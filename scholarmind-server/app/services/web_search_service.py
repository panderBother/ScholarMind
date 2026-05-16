"""Web 对话联网搜索：复用 scholarmind-mcp/web_search。"""

from __future__ import annotations

import os

from app.core.config import settings
from app.core.logging_setup import log_info
from web_search.operations import format_results_markdown, web_search_for_message

__all__ = ["fetch_web_context_markdown", "is_configured"]


def is_configured() -> bool:
    """Brave Key 可选；无 Key 时使用 DuckDuckGo 回退。"""
    return bool(settings.web_search_enabled)


def _apply_search_env() -> None:
    key = (settings.brave_search_api_key or "").strip()
    if key:
        os.environ["BRAVE_SEARCH_API_KEY"] = key


async def fetch_web_context_markdown(query: str) -> str:
    if not settings.web_search_enabled:
        return ""
    q = (query or "").strip()
    if not q:
        return ""
    _apply_search_env()
    log_info("[web_search] 查询 query=%r", q[:120])
    payload = await web_search_for_message(q, max_results=settings.web_search_max_results)
    md = format_results_markdown(payload)
    log_info(
        "[web_search] 完成 provider=%s hits=%s",
        payload.get("provider"),
        len(payload.get("results") or []),
    )
    return md
