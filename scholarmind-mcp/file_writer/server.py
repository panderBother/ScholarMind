"""文件写入 MCP Server（骨架）：将报告写入受控目录（沙箱路径）。"""


def tool_write_markdown(filename: str, content: str) -> dict:
    _ = content
    return {"filename": filename, "status": "skipped_stub"}
