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
from app.ingest.registry import detect_file_type, parse_file, requires_preview
from app.ingest.types import SUPPORTED_EXTENSIONS, FileType
from app.models.orm import Document, KnowledgeBase, KnowledgeItem, new_uuid
from app.schemas.document import (
    DocumentConfirmImportResponse,
    DocumentOut,
    DocumentParsedContentOut,
    DocumentParsedContentUpdate,
    DocumentUploadResponse,
)
from app.services import item_indexing
from app.storage import get_blob_storage
from app.utils.db_text import clamp_mediumtext

log = logging.getLogger(__name__)

PDF_MAGIC = b"%PDF"
ZIP_MAGIC = b"PK\x03\x04"


def _safe_filename(name: str | None, fallback: str = "upload.bin") -> str:
    if not name:
        return fallback
    base = Path(name).name
    base = re.sub(r"[^\w.\-()\s\u4e00-\u9fff]", "_", base, flags=re.UNICODE).strip()
    return base or fallback


def _validate_file_magic(data: bytes, file_type: FileType, filename: str) -> None:
    ext = Path(filename).suffix.lower()
    if file_type == FileType.PDF and not data.startswith(PDF_MAGIC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不是有效 PDF：{filename}")
    if file_type in (FileType.DOCX, FileType.XLSX) and not data.startswith(ZIP_MAGIC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不是有效 {ext} 文件：{filename}")
    if file_type == FileType.DOC and not (data.startswith(b"\xd0\xcf\x11\xe0") or data[:4] == ZIP_MAGIC):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"不是有效 Word 文件：{filename}")


def _mime_for_type(file_type: FileType) -> str:
    from app.ingest.types import MIME_BY_TYPE

    return MIME_BY_TYPE.get(file_type, "application/octet-stream")


async def _ensure_kb(session: AsyncSession, user_id: str, kb_id: str) -> KnowledgeBase:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "知识库不存在")
    return kb


def _parse_sync(path: str, filename: str, file_type: FileType):
    return parse_file(path, filename, file_type)


async def upload_documents(
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
            f"单次最多上传 {s.pdf_max_batch} 个文件",
        )
    await _ensure_kb(session, user_id, kb_id)

    max_bytes = s.pdf_max_upload_mb * 1024 * 1024
    storage = get_blob_storage()
    created: list[Document] = []
    skipped = 0
    needs_preview: list[str] = []

    for up in files:
        raw_name = _safe_filename(up.filename)
        ext = Path(raw_name).suffix.lower()
        if ext not in SUPPORTED_EXTENSIONS:
            supported = ", ".join(sorted(SUPPORTED_EXTENSIONS))
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"不支持的格式「{ext or raw_name}」。支持：{supported}",
            )
        file_type = detect_file_type(raw_name)
        data = await up.read()
        if len(data) > max_bytes:
            raise HTTPException(
                status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                f"文件过大（上限 {s.pdf_max_upload_mb}MB）：{raw_name}",
            )
        _validate_file_magic(data, file_type, raw_name)

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
            file_type=file_type.value,
            storage_key=key,
            status="pending",
            file_bytes=len(data),
            md5=md5_hex,
        )

        if requires_preview(file_type):
            doc.status = "preview"
            doc.parse_stage = "解析预览"
            try:
                fspath = storage.filesystem_path(key)
                result = await asyncio.to_thread(_parse_sync, fspath, raw_name, file_type)
                doc.parsed_content = clamp_mediumtext(result.merged_content())
                doc.parsed_title = result.title
                doc.parsed_summary = result.summary
                doc.title = result.title
                doc.parse_progress = 100
                doc.parse_stage = "待确认"
            except Exception as e:
                doc.status = "failed"
                doc.error_message = str(e)[:4000]
                doc.parse_stage = "解析失败"
                log.exception("preview parse failed doc=%s", doc_id)

        session.add(doc)
        created.append(doc)

    await session.commit()

    from app.workers.document_tasks import process_document_task, run_document_ingest

    out: list[DocumentOut] = []
    for d in created:
        await session.refresh(d)
        out.append(DocumentOut.model_validate(d))
        if d.status == "preview":
            needs_preview.append(d.id)
            continue
        if d.status == "failed":
            continue
        if s.ingest_background_thread:
            log.info("ingest queue (BackgroundTasks): doc=%s", d.id)
            background_tasks.add_task(run_document_ingest, d.id)
        else:
            process_document_task.delay(d.id)

    return DocumentUploadResponse(documents=out, skipped_duplicates=skipped, needs_preview=needs_preview)


# 兼容旧名
upload_pdfs = upload_documents


async def get_parsed_content(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
) -> DocumentParsedContentOut:
    doc = await get_document(session, user_id, kb_id, doc_id)
    if doc.status not in ("preview", "done", "pending", "processing"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "当前文档无预览内容")
    content = doc.parsed_content
    if not content and doc.status == "done":
        raise HTTPException(status.HTTP_404_NOT_FOUND, "该文档已完成自动解析，请查看解析条目")
    if not content:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "预览内容为空")
    return DocumentParsedContentOut(
        doc_id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        title=doc.parsed_title or doc.title,
        summary=doc.parsed_summary,
        content=content,
        status=doc.status,
    )


async def update_parsed_content(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
    body: DocumentParsedContentUpdate,
) -> DocumentParsedContentOut:
    doc = await get_document(session, user_id, kb_id, doc_id)
    if doc.status != "preview":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅「待预览」状态的文档可编辑")
    doc.parsed_content = clamp_mediumtext(body.content.strip()) or ""
    if body.title is not None:
        doc.parsed_title = body.title.strip()[:512] or None
        doc.title = doc.parsed_title
    if body.summary is not None:
        doc.parsed_summary = body.summary.strip()[:500] or None
    await session.commit()
    await session.refresh(doc)
    return DocumentParsedContentOut(
        doc_id=doc.id,
        filename=doc.filename,
        file_type=doc.file_type,
        title=doc.parsed_title or doc.title,
        summary=doc.parsed_summary,
        content=doc.parsed_content or "",
        status=doc.status,
    )


async def confirm_document_import(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
) -> DocumentConfirmImportResponse:
    doc = await get_document(session, user_id, kb_id, doc_id)
    if doc.status != "preview":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "仅「待预览」状态的文档可确认入库")
    if not (doc.parsed_content or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "预览内容为空，请先编辑或重新上传")

    doc.status = "pending"
    doc.error_message = None
    doc.parse_progress = 0
    doc.parse_stage = "排队中"
    await session.commit()
    await session.refresh(doc)

    from app.workers.document_tasks import process_document_task, run_document_ingest

    settings = get_settings()
    if settings.ingest_background_thread:
        background_tasks.add_task(run_document_ingest, doc.id)
    else:
        process_document_task.delay(doc.id)

    return DocumentConfirmImportResponse(document=DocumentOut.model_validate(doc))


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
    doc.parse_progress = 0
    doc.parse_stage = "排队中"
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


def document_media_type(doc: Document) -> str:
    ext = Path(doc.filename).suffix.lower()
    ext_mime = {
        ".pdf": "application/pdf",
        ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ".doc": "application/msword",
        ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        ".xls": "application/vnd.ms-excel",
        ".csv": "text/csv",
        ".md": "text/markdown",
        ".markdown": "text/markdown",
        ".txt": "text/plain",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".webp": "image/webp",
    }
    if ext in ext_mime:
        return ext_mime[ext]
    ft = FileType(doc.file_type) if doc.file_type else FileType.PDF
    from app.ingest.types import MIME_BY_TYPE

    return MIME_BY_TYPE.get(ft, "application/octet-stream")


async def delete_document(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    doc_id: str,
) -> None:
    """删除文档文件、关联解析条目及检索索引。"""
    doc = await get_document(session, user_id, kb_id, doc_id)
    q = await session.execute(select(KnowledgeItem).where(KnowledgeItem.document_id == doc_id))
    items = list(q.scalars().all())

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

    await asyncio.to_thread(item_indexing.remove_index_for_document, doc_id)
