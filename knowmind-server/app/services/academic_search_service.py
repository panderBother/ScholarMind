"""对话学术检索：arXiv + Semantic Scholar（复用 knowmind-mcp）。"""

from __future__ import annotations

import os

from app.core.config import settings
from app.core.logging_setup import log_info
from arxiv.operations import format_arxiv_markdown, search_arxiv
from semantic_scholar.operations import format_semantic_scholar_markdown, search_semantic_scholar

__all__ = [
    "fetch_arxiv_context_markdown",
    "fetch_semantic_scholar_context_markdown",
]


def _apply_s2_env() -> None:
    key = (settings.semantic_scholar_api_key or "").strip()
    if key:
        os.environ["SEMANTIC_SCHOLAR_API_KEY"] = key


async def fetch_arxiv_context_markdown(query: str) -> str:
    if not settings.arxiv_search_enabled:
        return ""
    q = (query or "").strip()
    if not q:
        return ""
    log_info("[arxiv] 查询 query=%r", q[:120])
    payload = await search_arxiv(q, max_results=settings.arxiv_max_results)
    md = format_arxiv_markdown(payload)
    log_info("[arxiv] 完成 hits=%s", len(payload.get("items") or []))
    return md


async def fetch_semantic_scholar_context_markdown(query: str) -> str:
    if not settings.semantic_scholar_enabled:
        return ""
    q = (query or "").strip()
    if not q:
        return ""
    _apply_s2_env()
    log_info("[semantic_scholar] 查询 query=%r", q[:120])
    payload = await search_semantic_scholar(q, max_results=settings.semantic_scholar_max_results)
    md = format_semantic_scholar_markdown(payload)
    log_info("[semantic_scholar] 完成 hits=%s", len(payload.get("papers") or []))
    return md
