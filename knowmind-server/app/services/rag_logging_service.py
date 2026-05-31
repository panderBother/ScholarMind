from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import RagRetrievalLog, new_uuid


@dataclass
class RagHit:
    chunk_id: str
    text: str
    doc_id: str
    item_id: str
    page: int
    score: float


@dataclass
class RagSearchResult:
    markdown: str
    hits: list[RagHit]
    avg_score: float
    top_item_ids: list[str]
    candidate_count: int = 0
    top_candidate_score: float = 0.0


def distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


def filter_confident_rag_hits(
    hits: list[RagHit],
    *,
    min_top_score: float,
    relative_to_top: float = 0.75,
    max_hits: int = 8,
) -> list[RagHit]:
    """对话引用：仅保留与 top1 足够接近的高分片段，避免整库灌水。"""
    if not hits:
        return []
    ordered = sorted(hits, key=lambda h: h.score, reverse=True)
    top = ordered[0].score
    if top < min_top_score:
        return []
    floor = top * relative_to_top
    return [h for h in ordered if h.score >= floor][:max_hits]


def normalize_topic_key(query: str) -> str:
    q = (query or "").strip().lower()
    return q[:200] if q else "unknown"


async def log_rag_retrieval(
    session: AsyncSession,
    *,
    user_id: str,
    kb_id: str,
    query: str,
    conversation_id: str | None,
    hits: list[RagHit],
) -> None:
    scores = [h.score for h in hits]
    avg = sum(scores) / len(scores) if scores else 0.0
    item_ids = [h.item_id for h in hits if h.item_id][:10]
    row = RagRetrievalLog(
        id=new_uuid(),
        user_id=user_id,
        kb_id=kb_id,
        conversation_id=conversation_id,
        query_text=query[:4000],
        hit_count=len(hits),
        avg_score=avg,
        hit_scores=scores,
        top_item_ids=item_ids,
    )
    session.add(row)
    await session.flush()

    from app.services.usage_analytics_service import record_rag_cites

    await record_rag_cites(
        session,
        user_id=user_id,
        kb_id=kb_id,
        conversation_id=conversation_id,
        hits=hits,
    )
