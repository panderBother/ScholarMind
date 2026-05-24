from __future__ import annotations

import logging
import threading
from datetime import UTC, datetime

from app.core.config import get_settings
from app.db.sync_session import session_scope
from app.ingest.chunking import chunk_pages
from app.ingest.embedding import embed_texts
from app.ingest.pdf import extract_pdf_pages
from app.indexing.vector_factory import get_vector_index
from app.indexing.whoosh_index import whoosh_upsert_chunks
from app.models.orm import Document, KnowledgeBase, KnowledgeItem, new_uuid
from app.services.item_indexing import build_index_row
from app.services.knowledge_category_service import get_or_create_default_category_sync
from app.storage.local import LocalBlobStorage
from app.workers.celery_app import celery_app

log = logging.getLogger(__name__)

_ingest_serial_holder: list[threading.BoundedSemaphore | None] = [None]


def _ingest_serial_lock() -> threading.BoundedSemaphore:
    if _ingest_serial_holder[0] is None:
        _ingest_serial_holder[0] = threading.BoundedSemaphore(max(1, min(8, get_settings().ingest_max_parallel)))
    return _ingest_serial_holder[0]


def _fail(document_id: str, message: str) -> None:
    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            return
        doc.status = "failed"
        doc.error_message = message[:4000]


def _reopen_pending(document_id: str) -> None:
    """嵌入/入库异常后允许下一轮重试（否则会永久卡在 processing）。"""
    try:
        with session_scope() as s:
            doc = s.get(Document, document_id)
            if doc is None:
                return
            if doc.status == "processing":
                doc.status = "pending"
                log.warning("ingest %s: reset pending after error (was processing)", document_id)
    except Exception:
        log.exception("ingest %s: failed to reset pending", document_id)


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
        if doc.status not in ("pending", "processing"):
            log.warning("ingest %s: unexpected status=%s, skip", document_id, doc.status)
            return False
        if doc.status == "pending":
            doc.status = "processing"
        kb_id = doc.kb_id
        user_id = doc.user_id
        storage_key = doc.storage_key
        doc_pk = doc.id
        filename = doc.filename

    settings = get_settings()
    storage = LocalBlobStorage(settings.storage_local_root)
    pdf_path = storage.filesystem_path(storage_key)

    log.info("ingest %s: extracting pdf %s", document_id, pdf_path)
    pages = extract_pdf_pages(pdf_path)
    log.info("ingest %s: pages=%s chunking", document_id, len(pages))
    chunks = chunk_pages(pages)
    texts = [ch.text for ch in chunks]
    log.info("ingest %s: chunks=%s embedding", document_id, len(texts))
    vectors = embed_texts(texts) if texts else []
    now = datetime.now(UTC)
    rows: list[dict] = []
    item_records: list[KnowledgeItem] = []

    with session_scope() as s:
        default_category_id = get_or_create_default_category_sync(s, kb_id, user_id)

    base_name = (filename or "document").rsplit(".", 1)[0][:80]
    for ch, vec in zip(chunks, vectors, strict=True):
        cid = new_uuid()
        item_id = new_uuid()
        page_no = int(ch.page) + 1
        title = f"{base_name} · 第 {page_no} 页"
        snippet = (ch.text or "").strip()
        content = snippet[:8000] if snippet else "（空白页）"
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
        item_records.append(
            KnowledgeItem(
                id=item_id,
                kb_id=kb_id,
                user_id=user_id,
                document_id=doc_pk,
                category_id=default_category_id,
                source_type="document",
                title=title[:200],
                content=content,
                lifecycle_status="published",
                access_level="internal",
                source=filename,
                chunk_id=cid,
                page=ch.page,
                published_at=now,
            )
        )

    log.info("ingest %s: upserting %s chunks to vector + whoosh", document_id, len(rows))
    get_vector_index().upsert_chunks(rows)
    whoosh_upsert_chunks(settings.whoosh_index_root, rows)

    title: str | None = None
    if chunks:
        title = (chunks[0].text.split("\n")[0] or "").strip()[:512] or None

    with session_scope() as s:
        doc = s.get(Document, document_id)
        if doc is None:
            log.error("ingest %s: document vanished before commit done", document_id)
            return False
        doc.status = "done"
        doc.chunk_count = len(rows)
        if title:
            doc.title = title
        for item in item_records:
            s.add(item)
        kb = s.get(KnowledgeBase, doc.kb_id)
        if kb is not None:
            kb.doc_count = int(kb.doc_count or 0) + 1

    log.info("ingest %s: status=done chunks=%s", document_id, len(rows))
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
