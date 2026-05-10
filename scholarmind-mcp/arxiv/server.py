"""
arXiv MCP Server（骨架）：暴露按关键词 / ID 查询论文元数据的能力。

实现时可选用官方 MCP Python SDK 或 stdio JSON-RPC 协议。
"""

def tool_search_arxiv(query: str, max_results: int = 5) -> dict:
    """占位：返回结构化查询意图，后续对接 arXiv API。"""
    return {"query": query, "max_results": max_results, "items": []}
