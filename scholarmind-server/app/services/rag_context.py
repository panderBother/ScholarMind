"""对话前的知识库向量检索（按 kb_id 过滤），生成注入模型的上下文 Markdown。"""

from __future__ import annotations

import asyncio
import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.indexing.vector_factory import get_vector_index
from app.ingest.embedding import embed_texts
from app.models.orm import KnowledgeBase

log = logging.getLogger(__name__)


def _format_hits(hits: list[dict]) -> str:
    lines: list[str] = []
    for i, h in enumerate(hits, 1):
        text = str(h.get("text") or "").strip()
        if not text:
            continue
        snippet = text[:1800] + ("…" if len(text) > 1800 else "")
        doc_id = h.get("doc_id") or "?"
        page = h.get("page")
        lines.append(f"### 摘录 {i}（文档 `{doc_id}` · 第 {page} 页）\n{snippet}")
    return "\n\n".join(lines)


async def build_kb_context_markdown(
    session: AsyncSession,
    user_id: str,
    kb_id: str | None,
    query: str,
) -> str:
    """
    校验知识库归属后做向量检索，返回可拼进 system prompt 的 Markdown。
    未选库 / 无权限 / 无命中时返回说明性短文本或空字符串。
    """
    if not kb_id or not str(kb_id).strip():
        return ""

    kb = await session.get(KnowledgeBase, kb_id.strip())
    if kb is None or kb.user_id != user_id:
        log.warning("rag: kb %s not found or not owned by user", kb_id)
        return ""

    q = (query or "").strip()
    if not q:
        return "（知识库已选但未提供提问文本，无法检索。）"

    try:
        q_vectors = await asyncio.to_thread(embed_texts, [q[:8000]])
        qvec = q_vectors[0]
    except Exception as e:
        log.exception("rag embed query failed: %s", e)
        return f"（向量检索失败：{e!s}）"

    try:
        hits = get_vector_index().query_similar(
            kb_id=kb.id,
            query_embedding=qvec,
            top_k=max(1, settings.rag_top_k),
        )
    except Exception as e:
        log.exception("rag vector query failed: %s", e)
        return f"（向量库查询失败：{e!s}）"

    if not hits:
        return (
            "（已在知识库中检索，但未找到与当前问题足够相近的片段；"
            "若尚未上传 PDF 请先入库，或尝试改写问题关键词。）"
        )

    body = _format_hits(hits)
    log.info("rag: kb=%s hits=%s", kb.id, len(hits))
    return body
