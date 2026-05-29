"""KnowMind 知识库检索 MCP Server。"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from kb_search.operations import search_kb as api_search_kb

mcp = FastMCP(
    "KnowMind KB Search",
    instructions=(
        "当需要查询用户私有知识库中的已发布条目时，使用 search_kb。"
        "需配置环境变量 KNOWMIND_API_BASE、KNOWMIND_KB_ID、KNOWMIND_ACCESS_TOKEN。"
    ),
)


@mcp.tool()
async def search_kb(query: str, limit: int = 20) -> dict:
    """检索指定 KnowMind 知识库（混合语义 + 关键词）。"""
    return await api_search_kb(query, limit=limit)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
