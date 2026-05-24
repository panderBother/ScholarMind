"""
文件写入 MCP Server：当用户要求将内容保存为文档（如 Markdown）到指定路径时调用。
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from file_writer.operations import (
    list_allowed_roots_payload,
    read_document,
    write_document,
    write_markdown,
)
mcp = FastMCP(
    "KnowMind File Writer",
    instructions=(
        "当用户明确要求将内容写入文件、保存为 Markdown/文档、或指定路径（如 D 盘某文件）时，"
        "必须调用 write_document 或 write_markdown，传入完整目标路径与正文内容。"
        "需要读取已有文件时使用 read_document。不要只在聊天里展示全文而不落盘。"
    ),
)


@mcp.tool()
def write_document_tool(
    path: str,
    content: str,
    format: str = "auto",
    overwrite: bool = True,
) -> dict:
    """将内容写入指定文件路径。"""
    return write_document(path, content, format=format, overwrite=overwrite)  # type: ignore[arg-type]


@mcp.tool()
def write_markdown_tool(filename: str, content: str, overwrite: bool = True) -> dict:
    """将 Markdown 写入文件。"""
    return write_markdown(filename, content, overwrite=overwrite)


@mcp.tool()
def read_document_tool(path: str) -> dict:
    """读取受控路径下的文本文件。"""
    return read_document(path)


@mcp.tool()
def list_allowed_write_roots() -> dict:
    """列出当前允许读写的根目录。"""
    return list_allowed_roots_payload()


def tool_write_markdown(filename: str, content: str) -> dict:
    return write_markdown(filename, content)


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
