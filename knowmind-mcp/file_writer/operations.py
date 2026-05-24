"""文件读写核心逻辑（MCP 与 Web API 共用）。"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Literal

from file_writer.paths import allowed_roots, resolve_writable_path

log = logging.getLogger("file_writer")

Format = Literal["markdown", "text", "auto"]

DEFAULT_READ_MAX_BYTES = 512 * 1024


def _normalize_extension(path: Path, fmt: Format) -> Path:
    if fmt == "auto" or path.suffix:
        return path
    if fmt == "markdown":
        return path.with_suffix(".md")
    if fmt == "text":
        return path.with_suffix(".txt")
    return path


def list_allowed_roots_payload() -> dict:
    roots = [str(p) for p in allowed_roots()]
    return {"allowed_roots": roots, "hint_env": "FILE_WRITER_ALLOWED_ROOTS（分号分隔多个路径）"}


def read_document(path: str, *, max_bytes: int = DEFAULT_READ_MAX_BYTES) -> dict:
    target = resolve_writable_path(path)
    if not target.is_file():
        raise ValueError(f"不是文件或不存在: {target}")
    raw = target.read_bytes()
    truncated = False
    if len(raw) > max_bytes:
        raw = raw[:max_bytes]
        truncated = True
    text = raw.decode("utf-8", errors="replace")
    log.info("file_read ok path=%s bytes=%s truncated=%s", target, target.stat().st_size, truncated)
    return {
        "path": str(target),
        "content": text,
        "truncated": truncated,
        "size_bytes": target.stat().st_size,
        "status": "read",
    }


def write_document(
    path: str,
    content: str,
    *,
    format: Format = "auto",
    overwrite: bool = True,
) -> dict:
    resolved = resolve_writable_path(path)
    target = _normalize_extension(resolved, format)
    if target.exists() and not overwrite:
        raise ValueError(f"文件已存在，请设置 overwrite=true 或换路径: {target}")
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    nbytes = len(content.encode("utf-8"))
    log.info("file_write ok path=%s bytes=%s overwrite=%s", target, nbytes, overwrite)
    print(f"[file_writer] 已执行写入操作 path={target} bytes={nbytes}", flush=True)
    return {
        "path": str(target),
        "bytes_written": nbytes,
        "format": "utf-8 text",
        "status": "written",
    }


def write_markdown(filename: str, content: str, *, overwrite: bool = True) -> dict:
    target = _normalize_extension(resolve_writable_path(filename), "markdown")
    return write_document(str(target), content, format="auto", overwrite=overwrite)


def execute_tool(name: str, arguments_json: str, *, max_read_bytes: int = DEFAULT_READ_MAX_BYTES) -> str:
    """执行单条 OpenAI 风格 function 调用，返回给模型的 tool 消息正文（JSON 字符串）。"""
    try:
        args = json.loads(arguments_json) if arguments_json.strip() else {}
    except json.JSONDecodeError as e:
        return json.dumps({"error": f"参数 JSON 无效: {e}"}, ensure_ascii=False)

    if not isinstance(args, dict):
        return json.dumps({"error": "参数必须是 JSON 对象"}, ensure_ascii=False)

    try:
        if name == "read_document":
            result = read_document(str(args.get("path", "")), max_bytes=max_read_bytes)
        elif name == "write_document":
            result = write_document(
                str(args.get("path", "")),
                str(args.get("content", "")),
                format=args.get("format", "auto"),
                overwrite=bool(args.get("overwrite", True)),
            )
        elif name == "write_markdown":
            result = write_markdown(
                str(args.get("filename", args.get("path", ""))),
                str(args.get("content", "")),
                overwrite=bool(args.get("overwrite", True)),
            )
        elif name == "list_allowed_write_roots":
            result = list_allowed_roots_payload()
        else:
            result = {"error": f"未知工具: {name}"}
    except Exception as e:  # noqa: BLE001
        result = {"error": str(e)}
        log.warning("file_tool error name=%s err=%s", name, e)

    return json.dumps(result, ensure_ascii=False)
