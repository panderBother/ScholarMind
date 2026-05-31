"""对话前的知识库混合检索，生成注入模型的上下文 Markdown。"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings, settings
from app.models.orm import KnowledgeBase
from app.services.rag_logging_service import RagHit, RagSearchResult, filter_confident_rag_hits
from app.services.search_service import hybrid_search

log = logging.getLogger(__name__)

_EMPTY = RagSearchResult(
    markdown="",
    hits=[],
    avg_score=0.0,
    top_item_ids=[],
)


def _chat_min_relevance_score() -> float:
    embed_mode = (get_settings().embedding_mode or "bge").strip().lower()
    if embed_mode == "hash":
        return 0.0
    return settings.rag_chat_min_relevance_score


def _format_hits(hits: list[RagHit]) -> str:
    lines: list[str] = []
    for i, h in enumerate(hits, 1):
        text = (h.text or "").strip()
        if not text:
            continue
        snippet_limit = max(1, int(get_settings().chunk_max_chars))
        snippet = text[:snippet_limit] + ("…" if len(text) > snippet_limit else "")
        ref = h.item_id or h.doc_id or "?"
        lines.append(f"### 摘录 {i}（条目 `{ref}` · 第 {h.page + 1} 页 · 相关度 {h.score:.2f}）\n{snippet}")
    return "\n\n".join(lines)


async def search_kb(
    session: AsyncSession,
    user_id: str,
    kb_id: str | None,
    query: str,
) -> RagSearchResult:
    if not kb_id or not str(kb_id).strip():
        return _EMPTY

    kb = await session.get(KnowledgeBase, kb_id.strip())
    if kb is None or kb.user_id != user_id:
        log.warning("rag: kb %s not found or not owned by user", kb_id)
        return _EMPTY

    q = (query or "").strip()
    if not q:
        return _EMPTY

    try:
        use_rerank = not settings.rag_chat_skip_rerank
        fused = await hybrid_search(
            session,
            user_id,
            kb.id,
            q,
            limit=max(1, settings.rag_top_k),
            rerank=use_rerank,
            strict_fusion=True,
            allow_keyword_fallback=False,
        )
    except Exception as e:
        log.exception("rag hybrid search failed: %s", e)
        return _EMPTY

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

    candidate_count = len(hits)
    top_candidate_score = max((h.score for h in hits), default=0.0)

    hits = filter_confident_rag_hits(
        hits,
        min_top_score=_chat_min_relevance_score(),
        max_hits=max(1, settings.rag_top_k),
    )

    if not hits:
        if candidate_count > 0:
            log.info(
                "rag: kb=%s %s candidates filtered (top=%.3f min=%.2f)",
                kb.id,
                candidate_count,
                top_candidate_score,
                _chat_min_relevance_score(),
            )
        else:
            log.info("rag: kb=%s no confident hits for query", kb.id)
        return RagSearchResult(
            markdown="",
            hits=[],
            avg_score=0.0,
            top_item_ids=[],
            candidate_count=candidate_count,
            top_candidate_score=top_candidate_score,
        )

    scores = [h.score for h in hits]
    avg = sum(scores) / len(scores)
    item_ids = [h.item_id for h in hits if h.item_id][:10]
    body = _format_hits(hits)
    log.info("rag: kb=%s hits=%s avg=%.3f", kb.id, len(hits), avg)
    return RagSearchResult(
        markdown=body,
        hits=hits,
        avg_score=avg,
        top_item_ids=item_ids,
        candidate_count=candidate_count,
        top_candidate_score=top_candidate_score,
    )


async def build_kb_context_markdown(
    session: AsyncSession,
    user_id: str,
    kb_id: str | None,
    query: str,
) -> str:
    result = await search_kb(session, user_id, kb_id, query)
    return result.markdown
