"""Web 端受控文件读写：复用 scholarmind-mcp/file_writer 的路径白名单与操作。"""

from __future__ import annotations

from app.core.config import settings

FILE_TOOLS_SYSTEM_HINT = (
    "用户已开启「本地文件读写」。当用户要求将内容保存为 Markdown/文档、读取或写入指定路径"
    "（例如 D 盘某文件）时，你必须调用工具 read_document / write_document / write_markdown 完成，"
    "不要仅在回复中粘贴全文而不实际读写磁盘。写入成功后简要告知用户路径。"
)
from file_writer.operations import (
    execute_tool,
    list_allowed_roots_payload,
    read_document,
    write_document,
    write_markdown,
)
from file_writer.paths import allowed_roots

__all__ = [
    "allowed_roots",
    "execute_tool",
    "list_allowed_roots_payload",
    "read_document",
    "write_document",
    "write_markdown",
    "max_read_bytes",
]


def max_read_bytes() -> int:
    return settings.file_read_max_bytes
