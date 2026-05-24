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


def distance_to_score(distance: float | None) -> float:
    if distance is None:
        return 0.0
    return max(0.0, min(1.0, 1.0 - float(distance)))


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
