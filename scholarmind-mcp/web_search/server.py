"""联网搜索 MCP Server。"""

from mcp.server.fastmcp import FastMCP

from web_search.operations import format_results_markdown, web_search

mcp = FastMCP(
    "ScholarMind Web Search",
    instructions="当用户需要实时信息、新闻、网页内容时使用 web_search 工具。",
)


@mcp.tool()
async def search_web(query: str, max_results: int = 5) -> dict:
    """联网搜索并返回结构化结果。"""
    payload = await web_search(query, max_results=max_results)
    payload["markdown"] = format_results_markdown(payload)
    return payload


def tool_web_search(query: str) -> dict:
    """同步占位（历史兼容）。"""
    import asyncio

    return asyncio.run(web_search(query))


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
