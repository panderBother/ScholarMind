from __future__ import annotations

import json
import logging
import re
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.orm import KnowledgeGap, RagRetrievalLog, UserFeedback, new_uuid
from app.services.edgefn_client import complete_chat_turn
from app.services.knowledge_category_service import ensure_default_category
from app.services.knowledge_item_service import create_item
from app.services.rag_logging_service import normalize_topic_key

log = logging.getLogger(__name__)


class DistillError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


def _thresholds() -> tuple[int, float, int]:
    s = get_settings()
    if getattr(s, "distill_demo_mode", True):
        return (2, 0.6, 1)
    return (5, 0.6, 3)


async def list_gaps(session: AsyncSession, user_id: str, kb_id: str) -> list[KnowledgeGap]:
    q = (
        select(KnowledgeGap)
        .where(
            KnowledgeGap.kb_id == kb_id,
            KnowledgeGap.user_id == user_id,
            KnowledgeGap.status.in_(("open", "draft_generated")),
        )
        .order_by(KnowledgeGap.updated_at.desc())
    )
    r = await session.execute(q)
    return list(r.scalars().all())


async def analyze_gaps(session: AsyncSession, user_id: str, kb_id: str) -> list[KnowledgeGap]:
    min_count, score_thr, fb_min = _thresholds()
    since = datetime.now(UTC) - timedelta(days=7 if not get_settings().distill_demo_mode else 1)

    log_q = select(RagRetrievalLog).where(
        RagRetrievalLog.kb_id == kb_id,
        RagRetrievalLog.user_id == user_id,
        RagRetrievalLog.created_at >= since,
    )
    logs = list((await session.execute(log_q)).scalars().all())

    clusters: dict[str, list[RagRetrievalLog]] = defaultdict(list)
    for row in logs:
        key = normalize_topic_key(row.query_text)
        clusters[key].append(row)

    created: list[KnowledgeGap] = []
    for key, rows in clusters.items():
        if len(rows) < min_count:
            continue
        scores = [float(r.avg_score or 0) for r in rows]
        avg = sum(scores) / len(scores) if scores else 0.0
        if avg >= score_thr:
            continue
        sample = list(dict.fromkeys(r.query_text for r in rows))[:5]
        gap = await _upsert_gap(
            session,
            kb_id=kb_id,
            user_id=user_id,
            gap_key=key,
            trigger_rule="high_miss",
            sample_queries=sample,
            avg_score=avg,
            hit_count=len(rows),
        )
        created.append(gap)

    fb_q = select(UserFeedback).where(
        UserFeedback.kb_id == kb_id,
        UserFeedback.user_id == user_id,
        UserFeedback.created_at >= since,
    )
    fbs = list((await session.execute(fb_q)).scalars().all())
    fb_clusters: dict[str, list[UserFeedback]] = defaultdict(list)
    for fb in fbs:
        key = fb.topic_key or normalize_topic_key(fb.query_text or fb.correction)
        fb_clusters[key].append(fb)

    for key, rows in fb_clusters.items():
        if len(rows) < fb_min:
            continue
        sample = list(dict.fromkeys((r.query_text or r.correction) for r in rows))[:5]
        gap = await _upsert_gap(
            session,
            kb_id=kb_id,
            user_id=user_id,
            gap_key=key,
            trigger_rule="user_correction",
            sample_queries=sample,
            avg_score=None,
            hit_count=len(rows),
        )
        created.append(gap)

    await session.commit()
    return await list_gaps(session, user_id, kb_id)


async def _upsert_gap(
    session: AsyncSession,
    *,
    kb_id: str,
    user_id: str,
    gap_key: str,
    trigger_rule: str,
    sample_queries: list[str],
    avg_score: float | None,
    hit_count: int,
) -> KnowledgeGap:
    q = select(KnowledgeGap).where(
        KnowledgeGap.kb_id == kb_id,
        KnowledgeGap.gap_key == gap_key,
        KnowledgeGap.status == "open",
    )
    existing = (await session.execute(q)).scalar_one_or_none()
    if existing:
        existing.sample_queries = sample_queries
        existing.avg_score = avg_score
        existing.hit_count = hit_count
        existing.trigger_rule = trigger_rule
        existing.updated_at = datetime.now(UTC)
        return existing
    gap = KnowledgeGap(
        id=new_uuid(),
        kb_id=kb_id,
        user_id=user_id,
        gap_key=gap_key,
        trigger_rule=trigger_rule,
        sample_queries=sample_queries,
        avg_score=avg_score,
        hit_count=hit_count,
        status="open",
    )
    session.add(gap)
    await session.flush()
    return gap


async def generate_drafts_for_gap(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    gap_id: str,
) -> list[dict]:
    gap = await session.get(KnowledgeGap, gap_id)
    if gap is None or gap.kb_id != kb_id or gap.user_id != user_id:
        raise DistillError("知识缺口不存在", 404)

    queries = "\n".join(f"- {q}" for q in (gap.sample_queries or [])[:5])
    prompt = f"""你是知识库编辑。用户多次提问但知识库检索命中质量低。请根据下列样例问题，生成 1-2 条**应写入知识库**的条目草稿。
输出**仅** JSON 数组：
[{{"title":"...", "content":"...", "tags":["..."]}}]
要求：content 为 Markdown，可独立理解，勿编造无依据细节，中文。

样例问题：
{queries}
"""
    turn = await complete_chat_turn([{"role": "user", "content": prompt}])
    text = (turn.content or "").strip()
    m = re.search(r"\[[\s\S]*\]", text)
    if not m:
        raise DistillError("LLM 未返回有效草稿 JSON")
    drafts = json.loads(m.group(0))
    if not isinstance(drafts, list):
        raise DistillError("草稿格式错误")

    cat = await ensure_default_category(session, user_id, kb_id)
    item_ids: list[str] = []
    out: list[dict] = []
    for d in drafts[:3]:
        if not isinstance(d, dict):
            continue
        title = str(d.get("title") or "蒸馏草稿")[:200]
        content = str(d.get("content") or "").strip()
        if not content:
            continue
        tags = d.get("tags") if isinstance(d.get("tags"), list) else []
        item = await create_item(
            session,
            user_id,
            kb_id,
            title=title,
            content=content,
            category_id=cat.id,
            tags=[str(t) for t in tags][:10],
            source=f"distill:{gap.trigger_rule}",
            source_type="distill",
            publish=False,
        )
        await session.flush()
        item_ids.append(item.id)
        out.append({"id": item.id, "title": item.title, "content": item.content, "lifecycle_status": item.lifecycle_status})

    gap.draft_item_ids = item_ids
    gap.status = "draft_generated"
    gap.updated_at = datetime.now(UTC)
    await session.commit()
    return out


async def record_feedback(
    session: AsyncSession,
    *,
    user_id: str,
    kb_id: str | None,
    conversation_id: str | None,
    message_id: str | None,
    query_text: str | None,
    correction: str,
) -> None:
    correction = correction.strip()
    if not correction:
        raise DistillError("纠错内容不能为空")
    topic = normalize_topic_key(query_text or correction)
    row = UserFeedback(
        id=new_uuid(),
        user_id=user_id,
        kb_id=kb_id,
        conversation_id=conversation_id,
        message_id=message_id,
        query_text=(query_text or "")[:4000] or None,
        correction=correction[:8000],
        topic_key=topic,
    )
    session.add(row)
    await session.commit()
