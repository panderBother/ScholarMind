"""对话前的知识库混合检索，生成注入模型的上下文 Markdown。"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.orm import KnowledgeBase
from app.services.rag_logging_service import RagHit, RagSearchResult
from app.services.search_service import hybrid_search

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
        use_rerank = not settings.rag_chat_skip_rerank
        fused = await hybrid_search(
            session,
            user_id,
            kb.id,
            q,
            limit=max(1, settings.rag_top_k),
            rerank=use_rerank,
        )
    except Exception as e:
        log.exception("rag hybrid search failed: %s", e)
        return RagSearchResult(
            markdown=f"（知识库检索失败：{e!s}）",
            hits=[],
            avg_score=0.0,
            top_item_ids=[],
        )

    hits: list[RagHit] = []
    for h in fused:
        hits.append(
            RagHit(
                chunk_id=h.chunk_id,
                text=h.text or h.snippet or h.title,
                doc_id=h.doc_id,
                item_id=h.item_id,
                page=int(h.page or 0),
                score=h.score,
            ),
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
