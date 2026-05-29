"""知识条目向量/全文索引写入与删除。"""

from __future__ import annotations

import logging
from typing import Any

from app.core.config import get_settings
from app.indexing.vector_factory import get_vector_index
from app.indexing.whoosh_index import (
    whoosh_delete_chunk,
    whoosh_delete_chunks,
    whoosh_delete_chunks_for_doc,
    whoosh_upsert_chunks,
)
from app.ingest.chunking import TextChunk, semantic_chunk_text
from app.ingest.embedding import embed_texts

log = logging.getLogger(__name__)


def build_index_row(
    *,
    chunk_id: str,
    kb_id: str,
    user_id: str,
    doc_id: str | None,
    item_id: str,
    page: int,
    text: str,
    vector: list[float],
    lifecycle_status: str,
) -> dict[str, Any]:
    return {
        "chunk_id": chunk_id,
        "kb_id": kb_id,
        "user_id": user_id,
        "doc_id": doc_id or "",
        "item_id": item_id,
        "page": page,
        "text": text,
        "vector": vector,
        "lifecycle_status": lifecycle_status,
    }


def upsert_index_rows(rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    get_vector_index().upsert_chunks(rows)
    whoosh_upsert_chunks(get_settings().whoosh_index_root, rows)


def _list_chunk_ids_for_doc(doc_id: str) -> list[str]:
    if not doc_id:
        return []
    idx = get_vector_index()
    list_fn = getattr(idx, "list_chunk_ids_for_doc", None)
    if callable(list_fn):
        return list_fn(doc_id)
    return []


def remove_index_for_document(doc_id: str) -> None:
    """删除某文档关联的全部检索段（向量 + Whoosh）。"""
    if not doc_id:
        return
    chunk_ids = _list_chunk_ids_for_doc(doc_id)
    if chunk_ids:
        get_vector_index().delete_chunks(chunk_ids)
        whoosh_delete_chunks(get_settings().whoosh_index_root, chunk_ids)
    whoosh_delete_chunks_for_doc(get_settings().whoosh_index_root, doc_id)


def remove_index_chunk(chunk_id: str | None) -> None:
    if not chunk_id:
        return
    remove_index_chunks([chunk_id])


def remove_index_chunks(chunk_ids: list[str]) -> None:
    ids = [c for c in chunk_ids if c]
    if not ids:
        return
    get_vector_index().delete_chunks(ids)
    root = get_settings().whoosh_index_root
    for cid in ids:
        whoosh_delete_chunk(root, cid)


def index_text_item(
    *,
    chunk_id: str,
    kb_id: str,
    user_id: str,
    item_id: str,
    text: str,
    lifecycle_status: str,
    doc_id: str | None = None,
    page: int = 0,
) -> str | None:
    """单段正文索引（手动条目等）；长文会语义切为多段、同一 item_id。返回首个 chunk_id。"""
    if doc_id:
        remove_index_for_document(doc_id)
    else:
        remove_index_chunk(chunk_id)
    rows, first_id = _build_rows_for_text(
        text=text,
        kb_id=kb_id,
        user_id=user_id,
        item_id=item_id,
        doc_id=doc_id,
        lifecycle_status=lifecycle_status,
        page=page,
    )
    upsert_index_rows(rows)
    return first_id


def reindex_document_item(
    *,
    kb_id: str,
    user_id: str,
    doc_id: str,
    item_id: str,
    text: str,
    lifecycle_status: str = "published",
) -> str | None:
    """
    文档条目：语义切分后写入索引，返回首个 chunk_id（兼容 item.chunk_id 字段）。
    """
    remove_index_for_document(doc_id)
    rows, first_id = _build_rows_for_text(
        text=text,
        kb_id=kb_id,
        user_id=user_id,
        item_id=item_id,
        doc_id=doc_id,
        lifecycle_status=lifecycle_status,
        page=0,
    )
    upsert_index_rows(rows)
    return first_id


def _build_rows_for_text(
    *,
    text: str,
    kb_id: str,
    user_id: str,
    item_id: str,
    doc_id: str | None,
    lifecycle_status: str,
    page: int,
) -> tuple[list[dict[str, Any]], str | None]:
    from app.models.orm import new_uuid

    body = (text or "").strip()
    if not body:
        body = " "
    chunks: list[TextChunk] = semantic_chunk_text(body, page=page)
    if not chunks:
        chunks = [TextChunk(text=body, page=page)]
    texts = [c.text for c in chunks]
    vectors = embed_texts(texts)
    rows: list[dict[str, Any]] = []
    first_id: str | None = None
    for ch, vec in zip(chunks, vectors, strict=True):
        cid = new_uuid()
        if first_id is None:
            first_id = cid
        rows.append(
            build_index_row(
                chunk_id=cid,
                kb_id=kb_id,
                user_id=user_id,
                doc_id=doc_id,
                item_id=item_id,
                page=ch.page,
                text=ch.text,
                vector=vec,
                lifecycle_status=lifecycle_status,
            )
        )
    return rows, first_id
