"""知识使用热度：事件打点与聚合统计。"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import KnowledgeItem, KnowledgeUsageEvent
from app.services.knowledge_base_service import get_knowledge_base
from app.services.rag_logging_service import RagHit
from app.services.search_service import HybridSearchHit

log = logging.getLogger(__name__)

EVENT_SEARCH_HIT = "search_hit"
EVENT_RAG_CITE = "rag_cite"
EVENT_CHAT_TURN = "chat_turn"


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _since(days: int) -> datetime:
    d = max(1, min(int(days), 90))
    return _utc_now() - timedelta(days=d)


async def _resolve_item_id(session: AsyncSession, item_id: str | None) -> str | None:
    iid = (item_id or "").strip()
    if not iid:
        return None
    exists = await session.scalar(select(KnowledgeItem.id).where(KnowledgeItem.id == iid))
    return iid if exists else None


async def _resolve_document_id(session: AsyncSession, document_id: str | None) -> str | None:
    from app.models.orm import Document

    did = (document_id or "").strip()
    if not did:
        return None
    exists = await session.scalar(select(Document.id).where(Document.id == did))
    return did if exists else None


async def record_search_hits(
    session: AsyncSession,
    *,
    user_id: str,
    kb_id: str,
    hits: list[HybridSearchHit],
) -> None:
    if not hits:
        return
    rows: list[KnowledgeUsageEvent] = []
    for h in hits:
        item_id = await _resolve_item_id(session, h.item_id)
        doc_id = await _resolve_document_id(session, h.doc_id)
        rows.append(
            KnowledgeUsageEvent(
                user_id=user_id,
                kb_id=kb_id,
                item_id=item_id,
                document_id=doc_id,
                event_type=EVENT_SEARCH_HIT,
                conversation_id=None,
            ),
        )
    session.add_all(rows)
    await session.flush()


async def record_rag_cites(
    session: AsyncSession,
    *,
    user_id: str,
    kb_id: str,
    conversation_id: str | None,
    hits: list[RagHit],
) -> None:
    if not hits:
        return
    rows: list[KnowledgeUsageEvent] = []
    for h in hits:
        item_id = await _resolve_item_id(session, h.item_id)
        doc_id = await _resolve_document_id(session, h.doc_id)
        rows.append(
            KnowledgeUsageEvent(
                user_id=user_id,
                kb_id=kb_id,
                item_id=item_id,
                document_id=doc_id,
                event_type=EVENT_RAG_CITE,
                conversation_id=conversation_id,
            ),
        )
    session.add_all(rows)
    await session.flush()


async def record_chat_turn(
    session: AsyncSession,
    *,
    user_id: str,
    kb_id: str,
    conversation_id: str | None,
) -> None:
    session.add(
        KnowledgeUsageEvent(
            user_id=user_id,
            kb_id=kb_id,
            item_id=None,
            document_id=None,
            event_type=EVENT_CHAT_TURN,
            conversation_id=conversation_id,
        ),
    )
    await session.flush()


async def log_usage_safe(session: AsyncSession, coro_factory) -> None:
    """埋点失败不影响主流程。"""
    try:
        await coro_factory()
    except Exception as e:  # noqa: BLE001
        log.warning("usage analytics log failed: %s", e)


async def get_overview(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    *,
    days: int = 7,
) -> dict:
    await get_knowledge_base(session, user_id, kb_id)
    since = _since(days)

    async def _count(event_type: str) -> int:
        n = await session.scalar(
            select(func.count())
            .select_from(KnowledgeUsageEvent)
            .where(
                KnowledgeUsageEvent.kb_id == kb_id,
                KnowledgeUsageEvent.event_type == event_type,
                KnowledgeUsageEvent.created_at >= since,
            ),
        )
        return int(n or 0)

    chat_turns = await _count(EVENT_CHAT_TURN)
    search_hits = await _count(EVENT_SEARCH_HIT)
    rag_cites = await _count(EVENT_RAG_CITE)
    unique_users = await session.scalar(
        select(func.count(func.distinct(KnowledgeUsageEvent.user_id))).where(
            KnowledgeUsageEvent.kb_id == kb_id,
            KnowledgeUsageEvent.created_at >= since,
        ),
    )
    total_events = await session.scalar(
        select(func.count())
        .select_from(KnowledgeUsageEvent)
        .where(
            KnowledgeUsageEvent.kb_id == kb_id,
            KnowledgeUsageEvent.created_at >= since,
        ),
    )
    return {
        "days": max(1, min(int(days), 90)),
        "chat_turns": chat_turns,
        "search_hits": search_hits,
        "rag_cites": rag_cites,
        "unique_users": int(unique_users or 0),
        "total_events": int(total_events or 0),
    }


async def get_top_items(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    *,
    days: int = 7,
    limit: int = 10,
) -> list[dict]:
    await get_knowledge_base(session, user_id, kb_id)
    since = _since(days)
    cap = max(1, min(int(limit), 50))

    stmt = (
        select(
            KnowledgeUsageEvent.item_id,
            KnowledgeUsageEvent.event_type,
            func.count().label("cnt"),
        )
        .where(
            KnowledgeUsageEvent.kb_id == kb_id,
            KnowledgeUsageEvent.item_id.isnot(None),
            KnowledgeUsageEvent.created_at >= since,
        )
        .group_by(KnowledgeUsageEvent.item_id, KnowledgeUsageEvent.event_type)
    )
    rows = (await session.execute(stmt)).all()

    agg: dict[str, dict] = {}
    for item_id, event_type, cnt in rows:
        if not item_id:
            continue
        bucket = agg.setdefault(
            item_id,
            {"item_id": item_id, "count": 0, "search_hits": 0, "rag_cites": 0},
        )
        n = int(cnt or 0)
        bucket["count"] += n
        if event_type == EVENT_SEARCH_HIT:
            bucket["search_hits"] += n
        elif event_type == EVENT_RAG_CITE:
            bucket["rag_cites"] += n

    ordered = sorted(agg.values(), key=lambda x: x["count"], reverse=True)[:cap]
    if not ordered:
        return []

    item_ids = [r["item_id"] for r in ordered]
    title_rows = await session.execute(
        select(KnowledgeItem.id, KnowledgeItem.title).where(KnowledgeItem.id.in_(item_ids)),
    )
    titles = {iid: title for iid, title in title_rows.all()}

    out: list[dict] = []
    for row in ordered:
        iid = row["item_id"]
        out.append(
            {
                "item_id": iid,
                "title": titles.get(iid) or "未命名条目",
                "count": row["count"],
                "search_hits": row["search_hits"],
                "rag_cites": row["rag_cites"],
            },
        )
    return out


async def get_trend(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    *,
    days: int = 7,
) -> dict:
    await get_knowledge_base(session, user_id, kb_id)
    d = max(1, min(int(days), 90))
    since = _utc_now() - timedelta(days=d - 1)
    day_expr = func.date(KnowledgeUsageEvent.created_at)

    stmt = (
        select(
            day_expr.label("day"),
            KnowledgeUsageEvent.event_type,
            func.count().label("cnt"),
        )
        .where(
            KnowledgeUsageEvent.kb_id == kb_id,
            KnowledgeUsageEvent.created_at >= since.replace(
                hour=0, minute=0, second=0, microsecond=0
            ),
        )
        .group_by(day_expr, KnowledgeUsageEvent.event_type)
        .order_by(day_expr)
    )
    rows = (await session.execute(stmt)).all()

    by_day: dict[str, dict] = {}
    for day_val, event_type, cnt in rows:
        key = str(day_val)[:10]
        point = by_day.setdefault(
            key,
            {"date": key, "search_hit": 0, "rag_cite": 0, "chat_turn": 0, "total": 0},
        )
        n = int(cnt or 0)
        point["total"] += n
        if event_type == EVENT_SEARCH_HIT:
            point["search_hit"] += n
        elif event_type == EVENT_RAG_CITE:
            point["rag_cite"] += n
        elif event_type == EVENT_CHAT_TURN:
            point["chat_turn"] += n

    start = (_utc_now() - timedelta(days=d - 1)).date()
    points: list[dict] = []
    for i in range(d):
        key = (start + timedelta(days=i)).isoformat()
        points.append(
            by_day.get(
                key,
                {"date": key, "search_hit": 0, "rag_cite": 0, "chat_turn": 0, "total": 0},
            ),
        )
    return {"days": d, "points": points}
