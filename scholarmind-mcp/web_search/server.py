"""联网搜索 MCP Server（骨架）：对接合规搜索 API（如 Bing / Brave）。"""


def tool_web_search(query: str) -> dict:
    return {"query": query, "results": []}
