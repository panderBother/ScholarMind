"""知识条目向量/全文索引写入与删除。"""

from __future__ import annotations

from typing import Any

from app.core.config import get_settings
from app.indexing.vector_factory import get_vector_index
from app.indexing.whoosh_index import whoosh_delete_chunk, whoosh_upsert_chunks
from app.ingest.embedding import embed_texts


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
) -> None:
    vectors = embed_texts([text[:8000]]) if text.strip() else embed_texts([" "])
    row = build_index_row(
        chunk_id=chunk_id,
        kb_id=kb_id,
        user_id=user_id,
        doc_id=doc_id,
        item_id=item_id,
        page=page,
        text=text,
        vector=vectors[0],
        lifecycle_status=lifecycle_status,
    )
    upsert_index_rows([row])


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
