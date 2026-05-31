from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from sqlalchemy import select

from app.core.config import get_settings
from app.db.sync_session import session_scope
from app.ingest.chunking import chunk_settings_from_config, semantic_chunk_pages, semantic_chunk_text
from app.ingest.embedding import embed_texts
from app.ingest.registry import parse_file
from app.ingest.types import FileType, PageText
from app.indexing.vector_factory import get_vector_index
from app.indexing.whoosh_index import whoosh_upsert_chunks
from app.models.orm import Document, KnowledgeBase, KnowledgeItem, new_uuid
from app.services.item_indexing import build_index_row, remove_index_for_document
from app.services.knowledge_category_service import get_or_create_default_category_sync
from app.storage.local import LocalBlobStorage
from app.utils.db_text import clamp_mediumtext
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_ingest_serial_holder: list[threading.BoundedSemaphore | None] = [None]


def _ingest_serial_lock() -> threading.BoundedSemaphore:
    if _ingest_serial_holder[0] is None:
        _ingest_serial_holder[0] = threading.BoundedSemaphore(max(1, min(8, get_settings().ingest_max_parallel)))
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
        doc.status = "failed"
        doc.error_message = message[:4000]
        doc.parse_stage = "失败"


def _reopen_pending(document_id: str) -> None:
    """嵌入/入库异常后允许下一轮重试（否则会永久卡在 processing）。"""
    try:
        with session_scope() as s:
            doc = s.get(Document, document_id)
            if doc is None:
                return
            if doc.status == "processing":
                doc.status = "pending"
                doc.parse_progress = 0
                doc.parse_stage = "排队中"
                log.warning("ingest %s: reset pending after error (was processing)", document_id)
    except Exception:
        log.exception("ingest %s: failed to reset pending", document_id)


def _purge_document_items(doc_pk: str) -> None:
    """删除文档旧条目（兼容此前「一块一条目」数据）。"""
    with session_scope() as s:
        rows = s.execute(select(KnowledgeItem).where(KnowledgeItem.document_id == doc_pk))
        for item in rows.scalars().all():
            s.delete(item)


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
            doc.status = "processing"
            doc.parse_progress = 5
            doc.parse_stage = "开始解析"
        kb_id = doc.kb_id
        user_id = doc.user_id
        storage_key = doc.storage_key
        doc_pk = doc.id
        filename = doc.filename
        parsed_title = doc.parsed_title
        parsed_content = doc.parsed_content
        file_type_str = doc.file_type
        doc_title = doc.title

    remove_index_for_document(doc_pk)
    _purge_document_items(doc_pk)

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
    log.info("ingest %s: index_chunks=%s embedding", document_id, len(index_chunks))
    texts = [ch.text for ch in index_chunks]
    vectors = _embed_with_progress(document_id, texts)
    now = datetime.now(UTC)
    rows: list[dict] = []

    with session_scope() as s:
        default_category_id = get_or_create_default_category_sync(s, kb_id, user_id)

    base_name = (parsed_title or parse_title or filename or "document").rsplit(".", 1)[0][:80]
    item_id = new_uuid()
    first_chunk_id: str | None = None

    for ch, vec in zip(index_chunks, vectors, strict=True):
        cid = new_uuid()
        if first_chunk_id is None:
            first_chunk_id = cid
        rows.append(
            build_index_row(
                chunk_id=cid,
                kb_id=kb_id,
                user_id=user_id,
                doc_id=doc_pk,
                item_id=item_id,
                page=ch.page,
                text=ch.text,
                vector=vec,
                lifecycle_status="published",
            )
        )

    item_record = KnowledgeItem(
        id=item_id,
        kb_id=kb_id,
        user_id=user_id,
        document_id=doc_pk,
        category_id=default_category_id,
        source_type="document",
        title=base_name[:200],
        content=clamp_mediumtext(full_text) or full_text[:8000],
        summary=(parsed_title or parse_title or base_name)[:500] if (parsed_title or parse_title) else None,
        lifecycle_status="published",
        access_level="internal",
        source=filename,
        chunk_id=first_chunk_id,
        page=0,
        published_at=now,
    )

    _set_progress(document_id, 90, "写入索引")
    log.info("ingest %s: upserting %s index segments", document_id, len(rows))
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
        doc.status = "done"
        doc.chunk_count = len(rows)
        doc.parse_progress = 100
        doc.parse_stage = "完成"
        if title:
            doc.title = title
        if parsed_content is None or not (doc.parsed_content or "").strip():
            doc.parsed_content = clamp_mediumtext(full_text)
        if parsed_title is None and title:
            doc.parsed_title = title[:512]
        s.add(item_record)
        kb = s.get(KnowledgeBase, doc.kb_id)
        if kb is not None:
            kb.doc_count = int(kb.doc_count or 0) + 1

    log.info("ingest %s: status=done item=%s segments=%s", document_id, item_id, len(rows))
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
