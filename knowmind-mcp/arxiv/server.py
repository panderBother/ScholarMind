"""arXiv MCP Server：按关键词或 ID 查询文档元数据。"""

from __future__ import annotations

import asyncio

from arxiv.operations import format_arxiv_markdown, search_arxiv


async def tool_search_arxiv(query: str, max_results: int = 5) -> dict:
    payload = await search_arxiv(query, max_results=max_results)
    payload["markdown"] = format_arxiv_markdown(payload)
    return payload


def tool_search_arxiv_sync(query: str, max_results: int = 5) -> dict:
    return asyncio.run(tool_search_arxiv(query, max_results=max_results))
