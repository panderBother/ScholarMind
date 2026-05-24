from __future__ import annotations

import asyncio
import hashlib
import logging
import re
from pathlib import Path

from fastapi import BackgroundTasks, HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.orm import Document, KnowledgeBase, KnowledgeItem, new_uuid
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.services import item_indexing
from app.storage import get_blob_storage

PDF_MAGIC = b"%PDF"

log = logging.getLogger(__name__)


def _safe_filename(name: str | None) -> str:
    if not name:
        return "upload.pdf"
    base = Path(name).name
    base = re.sub(r"[^\w.\-()\s\u4e00-\u9fff]", "_", base, flags=re.UNICODE).strip()
    return base or "upload.pdf"


async def _ensure_kb(session: AsyncSession, user_id: str, kb_id: str) -> KnowledgeBase:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库不存在")
    return kb


async def upload_pdfs(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    files: list[UploadFile],
    background_tasks: BackgroundTasks,
) -> DocumentUploadResponse:
    s = get_settings()
    if len(files) > s.pdf_max_batch:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"单次最多上传 {s.pdf_max_batch} 个 PDF",
        )
    await _ensure_kb(session, user_id, kb_id)

    max_bytes = s.pdf_max_upload_mb * 1024 * 1024
    storage = get_blob_storage()
    created: list[Document] = []
    skipped = 0

    for up in files:
        raw_name = _safe_filename(up.filename)
        if not raw_name.lower().endswith(".pdf"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"仅支持 PDF：{raw_name}")
        data = await up.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"文件过大（上限 {s.pdf_max_upload_mb}MB）：{raw_name}",
            )
        if not data.startswith(PDF_MAGIC):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不是有效 PDF：{raw_name}")

        md5_hex = hashlib.md5(data).hexdigest()
        dup = await session.execute(
            select(Document).where(
                Document.kb_id == kb_id,
                Document.md5 == md5_hex,
                Document.status != "failed",
            )
        )
        if dup.scalar_one_or_none() is not None:
            skipped += 1
            continue

        doc_id = new_uuid()
        key = f"users/{user_id}/kb/{kb_id}/docs/{doc_id}/{raw_name}"
        await storage.put_bytes(key, data)

        doc = Document(
            id=doc_id,
            kb_id=kb_id,
            user_id=user_id,
            filename=raw_name,
            storage_key=key,
            status="pending",
            file_bytes=len(data),
            md5=md5_hex,
        )
        session.add(doc)
        created.append(doc)

    await session.commit()

    from app.workers.document_tasks import process_document_task, run_document_ingest

    out: list[DocumentOut] = []
    for d in created:
        await session.refresh(d)
        out.append(DocumentOut.model_validate(d))
        if s.ingest_background_thread:
            log.info("ingest queue (BackgroundTasks): doc=%s", d.id)
            background_tasks.add_task(run_document_ingest, d.id)
        else:
            process_document_task.delay(d.id)

    return DocumentUploadResponse(documents=out, skipped_duplicates=skipped)


async def list_documents(session: AsyncSession, user_id: str, kb_id: str) -> list[Document]:
    await _ensure_kb(session, user_id, kb_id)
    q = (
        select(Document)
        .where(Document.kb_id == kb_id)
        .order_by(Document.created_at.desc())
    )
    r = await session.execute(q)
    return list(r.scalars().all())


async def retry_document_parse(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
) -> DocumentOut:
    """对卡在 pending / 队列丢失的 failed 文档重新投递 Celery。"""
    await _ensure_kb(session, user_id, kb_id)
    doc = await session.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id or doc.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    if doc.status not in ("pending", "failed", "processing"):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "仅「待处理」「解析中」或「失败」的文档可重试解析",
        )
    doc.status = "pending"
    doc.error_message = None
    await session.commit()
    await session.refresh(doc)

    from app.workers.document_tasks import process_document_task, run_document_ingest

    settings = get_settings()
    if settings.ingest_background_thread:
        background_tasks.add_task(run_document_ingest, doc.id)
    else:
        process_document_task.delay(doc.id)
    return DocumentOut.model_validate(doc)


async def get_document(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
) -> Document:
    await _ensure_kb(session, user_id, kb_id)
    doc = await session.get(Document, doc_id)
    if doc is None or doc.kb_id != kb_id or doc.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档不存在")
    return doc


def document_filesystem_path(doc: Document) -> str:
    storage = get_blob_storage()
    path = Path(storage.filesystem_path(doc.storage_key))
    if not path.is_file():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "文档文件不存在")
    return str(path)


async def delete_document(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
) -> None:
    """删除文档 PDF、关联解析条目及检索索引。"""
    doc = await get_document(session, user_id, kb_id, doc_id)
    q = await session.execute(select(KnowledgeItem).where(KnowledgeItem.document_id == doc_id))
    items = list(q.scalars().all())
    chunk_ids = [i.chunk_id for i in items if i.chunk_id]

    for item in items:
        await session.delete(item)

    storage_key = doc.storage_key
    was_done = doc.status == "done"
    await session.delete(doc)

    kb = await session.get(KnowledgeBase, kb_id)
    if kb is not None and was_done:
        kb.doc_count = max(0, int(kb.doc_count or 0) - 1)

    await session.commit()

    storage = get_blob_storage()
    try:
        await storage.delete(storage_key)
    except Exception:
        log.warning("delete document %s: blob remove failed key=%s", doc_id, storage_key, exc_info=True)

    if chunk_ids:
        await asyncio.to_thread(item_indexing.remove_index_chunks, chunk_ids)
