"""Semantic Scholar MCP Server：文档检索与 TL;DR 摘要。"""

from __future__ import annotations

import asyncio

from semantic_scholar.operations import format_semantic_scholar_markdown, search_semantic_scholar


async def tool_semantic_scholar_search(query: str, max_results: int = 5) -> dict:
    payload = await search_semantic_scholar(query, max_results=max_results)
    payload["markdown"] = format_semantic_scholar_markdown(payload)
    return payload


def tool_semantic_scholar_search_sync(query: str, max_results: int = 5) -> dict:
    return asyncio.run(tool_semantic_scholar_search(query, max_results=max_results))
