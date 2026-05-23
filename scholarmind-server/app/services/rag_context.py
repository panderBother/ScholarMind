"""对话前的知识库向量检索（按 kb_id 过滤），生成注入模型的上下文 Markdown。"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.indexing.vector_factory import get_vector_index
from app.ingest.embedding import embed_texts
from app.models.orm import KnowledgeBase
from app.services.rag_logging_service import RagHit, RagSearchResult, distance_to_score

log = logging.getLogger(__name__)


def _format_hits(hits: list[RagHit]) -> str:
    lines: list[str] = []
    for i, h in enumerate(hits, 1):
        text = (h.text or "").strip()
        if not text:
            continue
        snippet = text[:1800] + ("…" if len(text) > 1800 else "")
        ref = h.item_id or h.doc_id or "?"
        lines.append(f"### 摘录 {i}（条目 `{ref}` · 第 {h.page + 1} 页 · 相关度 {h.score:.2f}）\n{snippet}")
    return "\n\n".join(lines)


async def search_kb(
    session: AsyncSession,
    user_id: str,
    kb_id: str | None,
    query: str,
) -> RagSearchResult:
    empty = RagSearchResult(
        markdown="",
        hits=[],
        avg_score=0.0,
        top_item_ids=[],
    )
    if not kb_id or not str(kb_id).strip():
        return empty

    kb = await session.get(KnowledgeBase, kb_id.strip())
    if kb is None or kb.user_id != user_id:
        log.warning("rag: kb %s not found or not owned by user", kb_id)
        return empty

    q = (query or "").strip()
    if not q:
        return RagSearchResult(
            markdown="（知识库已选但未提供提问文本，无法检索。）",
            hits=[],
            avg_score=0.0,
            top_item_ids=[],
        )

    try:
        q_vectors = await asyncio.to_thread(embed_texts, [q[:8000]])
        qvec = q_vectors[0]
    except Exception as e:
        log.exception("rag embed query failed: %s", e)
        return RagSearchResult(
            markdown=f"（向量检索失败：{e!s}）",
            hits=[],
            avg_score=0.0,
            top_item_ids=[],
        )

    try:
        raw_hits = get_vector_index().query_similar(
            kb_id=kb.id,
            query_embedding=qvec,
            top_k=max(1, settings.rag_top_k),
        )
    except Exception as e:
        log.exception("rag vector query failed: %s", e)
        return RagSearchResult(
            markdown=f"（向量库查询失败：{e!s}）",
            hits=[],
            avg_score=0.0,
            top_item_ids=[],
        )

    hits: list[RagHit] = []
    for h in raw_hits:
        score = distance_to_score(h.get("distance"))
        hits.append(
            RagHit(
                chunk_id=str(h.get("chunk_id") or ""),
                text=str(h.get("text") or ""),
                doc_id=str(h.get("doc_id") or ""),
                item_id=str(h.get("item_id") or ""),
                page=int(h.get("page") or 0),
                score=score,
            )
        )

    if not hits:
        return RagSearchResult(
            markdown=(
                "（已在知识库中检索，但未找到与当前问题足够相近的片段；"
                "若尚未上传 PDF 请先入库，或尝试改写问题关键词。）"
            ),
            hits=[],
            avg_score=0.0,
            top_item_ids=[],
        )

    scores = [h.score for h in hits]
    avg = sum(scores) / len(scores)
    item_ids = [h.item_id for h in hits if h.item_id][:10]
    body = _format_hits(hits)
    log.info("rag: kb=%s hits=%s avg=%.3f", kb.id, len(hits), avg)
    return RagSearchResult(markdown=body, hits=hits, avg_score=avg, top_item_ids=item_ids)


async def build_kb_context_markdown(
    session: AsyncSession,
    user_id: str,
    kb_id: str | None,
    query: str,
) -> str:
    result = await search_kb(session, user_id, kb_id, query)
    return result.markdown
