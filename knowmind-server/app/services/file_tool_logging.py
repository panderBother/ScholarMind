"""文件工具操作日志文案（服务端 logging + SSE file_log）。"""

from __future__ import annotations

from app.services.chat_file_tools import ToolTraceEntry


def tool_log_message(entry: ToolTraceEntry) -> str:
    r = entry.result
    if not entry.ok:
        err = r.get("error") if isinstance(r.get("error"), str) else "未知错误"
        return f"文件操作失败（{entry.name}）：{err}"

    path = r.get("path")
    path_s = str(path) if path else "（无路径）"

    if entry.name in ("write_document", "write_markdown"):
        nbytes = r.get("bytes_written")
        extra = f"，{nbytes} 字节" if isinstance(nbytes, int) else ""
        return f"已执行写入操作：{path_s}{extra}"

    if entry.name == "read_document":
        size = r.get("size_bytes")
        extra = f"，共 {size} 字节" if isinstance(size, int) else ""
        return f"已执行读取操作：{path_s}{extra}"

    if entry.name == "list_allowed_write_roots":
        n = len(r.get("allowed_roots") or [])
        return f"已查询允许目录：共 {n} 个根路径"

    return f"已执行 {entry.name}"
