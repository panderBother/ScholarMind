"""RAG 检索命中 → 前端可展示的引用来源结构（对话、报告共用）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import Document, KnowledgeItem
from app.services.rag_logging_service import RagHit


async def resolve_hit_titles(session: AsyncSession, hits: list[RagHit]) -> dict[str, str]:
    titles: dict[str, str] = {}
    item_ids = {h.item_id for h in hits if h.item_id}
    doc_ids = {h.doc_id for h in hits if h.doc_id}
    if item_ids:
        q = await session.execute(select(KnowledgeItem).where(KnowledgeItem.id.in_(item_ids)))
        for item in q.scalars().all():
            titles[item.id] = item.title
    if doc_ids:
        q = await session.execute(select(Document).where(Document.id.in_(doc_ids)))
        for doc in q.scalars().all():
            titles[doc.id] = doc.title or doc.filename
    return titles


def hits_to_source_payload(hits: list[RagHit], titles: dict[str, str]) -> list[dict]:
    out: list[dict] = []
    for i, h in enumerate(hits, 1):
        key = h.item_id or h.doc_id or h.chunk_id
        title = titles.get(key, f"摘录 {i}")
        snippet = (h.text or "").strip()
        if len(snippet) > 400:
            snippet = snippet[:400] + "…"
        meta_parts: list[str] = []
        if h.page is not None:
            meta_parts.append(f"第 {h.page + 1} 页")
        if h.score:
            meta_parts.append(f"相关度 {h.score:.2f}")
        out.append(
            {
                "index": i,
                "chunk_id": h.chunk_id or None,
                "item_id": h.item_id or None,
                "document_id": h.doc_id or None,
                "title": title,
                "meta": " · ".join(meta_parts) if meta_parts else None,
                "snippet": snippet,
                "page": h.page,
                "score": round(h.score, 4) if h.score else None,
            },
        )
    return out


async def build_rag_sources_payload(
    session: AsyncSession | None,
    hits: list[RagHit],
) -> list[dict]:
    if not hits:
        return []
    titles = await resolve_hit_titles(session, hits) if session is not None else {}
    return hits_to_source_payload(hits, titles)
