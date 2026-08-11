from __future__ import annotations

import logging
import threading
import hashlib
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.sync_session import session_scope
from app.ingest.chunking import (
    TextChunk,
    chunk_settings_from_config,
    semantic_chunk_pages,
    semantic_chunk_text,
)
from app.ingest.document_state import DocumentStatus, transition_document
from app.ingest.embedding import embed_texts
from app.ingest.registry import parse_file
from app.ingest.types import FileType, PageText
from app.indexing.vector_factory import get_vector_index
from app.indexing.whoosh_index import whoosh_upsert_chunks
from app.models.orm import Document, DocumentChunk, KnowledgeBase, KnowledgeItem, new_uuid
from app.services.item_indexing import build_index_row, remove_index_chunks
from app.services.knowledge_category_service import get_or_create_default_category_sync
from app.storage.local import LocalBlobStorage
from app.utils.db_text import clamp_mediumtext
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_ingest_serial_holder: list[threading.BoundedSemaphore | None] = [None]


def _ingest_serial_lock() -> threading.BoundedSemaphore:
    if _ingest_serial_holder[0] is None:
        _ingest_serial_holder[0] = threading.BoundedSemaphore(
            max(1, min(8, get_settings().ingest_max_parallel))
        )
    return _ingest_serial_holder[0]


def _set_progress(document_id: str, progress: int, stage: str | None = None) -> None:
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            return
        doc.parse_progress = max(0, min(100, progress))
        if stage is not None:
            doc.parse_stage = (stage or "")[:64] or None


def _fail(document_id: str, message: str) -> None:
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            return
        transition_document(
            doc,
            DocumentStatus.FAILED,
            stage="失败",
            error=message,
        )


def _reopen_pending(document_id: str) -> None:
    """嵌入/入库异常后允许下一轮重试（否则会永久卡在 processing）。"""
    try:
        with session_scope() as s:
            doc = s.get(Document, document_id)
            if doc is None:
                return
            if doc.status == "processing":
                transition_document(
                    doc,
                    DocumentStatus.PENDING,
                    progress=0,
                    stage="排队中",
                )
                log.warning("ingest %s: reset pending after error (was processing)", document_id)
    except Exception:
        log.exception("ingest %s: failed to reset pending", document_id)


def _chunk_hash(text: str, page: int) -> str:
    body = f"{int(page)}\0{(text or '').strip()}".encode("utf-8")
    return hashlib.sha256(body).hexdigest()


@dataclass(frozen=True)
class IncrementalChunkAssignment:
    chunk: TextChunk
    chunk_id: str
    content_hash: str
    requires_embedding: bool


def plan_incremental_chunks(
    *,
    document_id: str,
    new_chunks: list[TextChunk],
    old_chunks: list[DocumentChunk],
) -> tuple[list[IncrementalChunkAssignment], list[str]]:
    reusable: dict[str, deque[DocumentChunk]] = defaultdict(deque)
    for old in old_chunks:
        reusable[old.content_hash].append(old)

    assignments: list[IncrementalChunkAssignment] = []
    reused_ids: set[str] = set()
    hash_occurrences: dict[str, int] = defaultdict(int)
    for chunk in new_chunks:
        content_hash = _chunk_hash(chunk.text, chunk.page)
        matched = reusable[content_hash].popleft() if reusable[content_hash] else None
        occurrence = hash_occurrences[content_hash]
        hash_occurrences[content_hash] += 1
        chunk_id = (
            matched.chunk_id
            if matched is not None
            else str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"knowmind:{document_id}:{content_hash}:{occurrence}",
                )
            )
        )
        if matched is not None:
            reused_ids.add(chunk_id)
        assignments.append(
            IncrementalChunkAssignment(
                chunk=chunk,
                chunk_id=chunk_id,
                content_hash=content_hash,
                requires_embedding=matched is None,
            )
        )

    removed_ids = [old.chunk_id for old in old_chunks if old.chunk_id not in reused_ids]
    return assignments, removed_ids


def _extract_full_text(
    *,
    file_path: str,
    filename: str,
    file_type_str: str | None,
    parsed_content: str | None,
    parsed_title: str | None,
    doc_title: str | None,
) -> tuple[str, list[PageText], str | None]:
    """返回 (全文, 页列表, 标题提示)。"""
    if (parsed_content or "").strip():
        body = parsed_content.strip()
        return body, [PageText(page_index=0, text=body)], parsed_title or doc_title

    file_type = FileType(file_type_str) if file_type_str else FileType.PDF
    if file_type == FileType.PDF:
        from app.ingest.pdf import extract_pdf_pages

        pages = extract_pdf_pages(file_path)
        merged = "\n\n".join((p.text or "").strip() for p in pages if (p.text or "").strip())
        return merged, pages, None

    result = parse_file(file_path, filename, file_type)
    pages = result.pages if result.pages else [PageText(page_index=0, text=result.merged_content())]
    merged = result.merged_content()
    return merged, pages, result.title


def _semantic_index_chunks(
    *,
    full_text: str,
    pages: list[PageText],
) -> list:
    min_chars, max_chars, overlap = chunk_settings_from_config()
    if pages and len(pages) > 1:
        return semantic_chunk_pages(
            pages,
            max_chars=max_chars,
            min_chars=min_chars,
            overlap=overlap,
        )
    return semantic_chunk_text(
        full_text,
        max_chars=max_chars,
        min_chars=min_chars,
        overlap=overlap,
    )


def _embed_with_progress(document_id: str, texts: list[str]) -> list[list[float]]:
    if not texts:
        return []
    settings = get_settings()
    batch_size = max(1, settings.embedding_batch_size)
    vectors: list[list[float]] = []
    total = len(texts)
    for start in range(0, total, batch_size):
        batch = texts[start : start + batch_size]
        vectors.extend(embed_texts(batch))
        done = min(start + len(batch), total)
        pct = 50 + int(35 * done / total)
        _set_progress(document_id, pct, f"向量化 {done}/{total}")
    return vectors


def process_document_once(document_id: str) -> bool:
    """
    执行一轮解析入库。返回 True 表示已写到 done；False 表示未执行完成（含文档不存在、状态不允许）。
    允许 status=processing：视为上次中断后的恢复，从 pending 逻辑继续（先保持 processing）。
    """
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            log.error("ingest %s: document not found (sync DB 看不到该行？)", document_id)
            return False
        if doc.status == "done":
            log.info("ingest %s: already done, skip", document_id)
            return True
        if doc.status == "failed":
            log.warning("ingest %s: status=failed, skip (请先重试解析)", document_id)
            return False
        if doc.status == "preview":
            log.warning("ingest %s: status=preview, skip (请先确认预览)", document_id)
            return False
        if doc.status not in ("pending", "processing"):
            log.warning("ingest %s: unexpected status=%s, skip", document_id, doc.status)
            return False
        if doc.status == "pending":
            transition_document(
                doc,
                DocumentStatus.PROCESSING,
                progress=5,
                stage="开始解析",
            )
        kb_id = doc.kb_id
        user_id = doc.user_id
        storage_key = doc.storage_key
        doc_pk = doc.id
        filename = doc.filename
        parsed_title = doc.parsed_title
        parsed_content = doc.parsed_content
        file_type_str = doc.file_type
        doc_title = doc.title
        old_chunks = list(
            s.scalars(
                select(DocumentChunk)
                .where(DocumentChunk.document_id == doc_pk)
                .order_by(DocumentChunk.ordinal.asc())
            ).all()
        )
        old_item = s.scalar(select(KnowledgeItem).where(KnowledgeItem.document_id == doc_pk))
        old_item_id = old_item.id if old_item is not None else None

    settings = get_settings()
    storage = LocalBlobStorage(settings.storage_local_root)
    file_path = storage.filesystem_path(storage_key)

    log.info("ingest %s: parsing %s", document_id, file_path)
    _set_progress(document_id, 15, "提取文本")
    full_text, pages, parse_title = _extract_full_text(
        file_path=file_path,
        filename=filename or "document",
        file_type_str=file_type_str,
        parsed_content=parsed_content,
        parsed_title=parsed_title,
        doc_title=doc_title,
    )
    if not (full_text or "").strip():
        _fail(document_id, "未提取到文本内容")
        return False

    index_chunks = _semantic_index_chunks(full_text=full_text, pages=pages)
    _set_progress(document_id, 45, f"语义切块 {len(index_chunks)} 段")
    now = datetime.now(UTC)

    with session_scope() as s:
        default_category_id = get_or_create_default_category_sync(s, kb_id, user_id)

    base_name = (parsed_title or parse_title or filename or "document").rsplit(".", 1)[0][:80]
    item_id = old_item_id or new_uuid()

    assignments, removed_ids = plan_incremental_chunks(
        document_id=doc_pk,
        new_chunks=index_chunks,
        old_chunks=old_chunks,
    )
    changed = [entry for entry in assignments if entry.requires_embedding]
    reused_count = len(assignments) - len(changed)
    changed_vectors = _embed_with_progress(document_id, [entry.chunk.text for entry in changed])
    rows: list[dict] = []
    for assignment, vector in zip(changed, changed_vectors, strict=True):
        rows.append(
            build_index_row(
                chunk_id=assignment.chunk_id,
                kb_id=kb_id,
                user_id=user_id,
                doc_id=doc_pk,
                item_id=item_id,
                page=assignment.chunk.page,
                text=assignment.chunk.text,
                vector=vector,
                lifecycle_status="published",
            )
        )
    first_chunk_id = assignments[0].chunk_id if assignments else None

    _set_progress(
        document_id,
        90,
        f"增量索引 新增/修改 {len(rows)}，复用 {reused_count}，删除 {len(removed_ids)}",
    )
    if removed_ids:
        remove_index_chunks(removed_ids)
    if rows:
        get_vector_index().upsert_chunks(rows)
        whoosh_upsert_chunks(settings.whoosh_index_root, rows)

    title: str | None = parsed_title or parse_title
    if not title and full_text:
        title = (full_text.split("\n")[0] or "").strip()[:512] or None

    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            log.error("ingest %s: document vanished before commit done", document_id)
            return False
        transition_document(
            doc,
            DocumentStatus.DONE,
            progress=100,
            stage="完成",
        )
        doc.chunk_count = len(assignments)
        if title:
            doc.title = title
        if parsed_content is None or not (doc.parsed_content or "").strip():
            doc.parsed_content = clamp_mediumtext(full_text)
        if parsed_title is None and title:
            doc.parsed_title = title[:512]
        item_record = s.get(KnowledgeItem, item_id) if old_item_id else None
        if item_record is None:
            item_record = KnowledgeItem(
                id=item_id,
                kb_id=kb_id,
                user_id=user_id,
                document_id=doc_pk,
                category_id=default_category_id,
                source_type="document",
                lifecycle_status="published",
                access_level="internal",
                page=0,
                published_at=now,
            )
            s.add(item_record)
        item_record.title = base_name[:200]
        item_record.content = clamp_mediumtext(full_text) or full_text[:8000]
        item_record.summary = (
            (parsed_title or parse_title or base_name)[:500]
            if (parsed_title or parse_title)
            else None
        )
        item_record.source = filename
        item_record.chunk_id = first_chunk_id

        existing_rows = list(
            s.scalars(select(DocumentChunk).where(DocumentChunk.document_id == doc_pk)).all()
        )
        for existing in existing_rows:
            s.delete(existing)
        s.flush()
        for ordinal, assignment in enumerate(assignments):
            s.add(
                DocumentChunk(
                    document_id=doc_pk,
                    chunk_id=assignment.chunk_id,
                    content_hash=assignment.content_hash,
                    ordinal=ordinal,
                    page=assignment.chunk.page,
                    text=assignment.chunk.text,
                )
            )
        kb = s.get(KnowledgeBase, doc.kb_id)
        if kb is not None and old_item_id is None:
            kb.doc_count = int(kb.doc_count or 0) + 1

    log.info(
        "ingest %s: status=done item=%s total=%s changed=%s reused=%s removed=%s",
        document_id,
        item_id,
        len(assignments),
        len(rows),
        reused_count,
        len(removed_ids),
    )
    return True


def run_document_ingest(document_id: str) -> None:
    """Celery / BackgroundTasks 共用：串行 + 失败解锁 processing。"""
    log.info("ingest job start doc=%s", document_id)
    with _ingest_serial_lock():
        last_err: str | None = None
        for attempt in range(3):
            try:
                ok = process_document_once(document_id)
                if ok:
                    log.info("ingest job finished doc=%s", document_id)
                    return
                with session_scope() as s:
                    d = s.get(Document, document_id)
                    st = d.status if d else None
                if st == "done":
                    log.info("ingest job finished (already done) doc=%s", document_id)
                    return
                last_err = f"ingest incomplete (status={st})"
                log.warning("document %s attempt %s: %s", document_id, attempt, last_err)
            except Exception as e:  # noqa: BLE001
                last_err = repr(e)
                log.exception("document %s ingest attempt %s failed", document_id, attempt)
                _reopen_pending(document_id)
        log.error("ingest job giving up doc=%s", document_id)
        _fail(document_id, last_err or "unknown error")


@celery_app.task(name="documents.process_document")
def process_document_task(document_id: str) -> None:
    run_document_ingest(document_id)
