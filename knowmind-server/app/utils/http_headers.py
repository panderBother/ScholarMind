from __future__ import annotations

from urllib.parse import quote


def attachment_content_disposition(filename: str, *, fallback_stem: str = "report") -> str:
    """Content-Disposition 支持中文文件名（RFC 5987），避免 latin-1 编码错误。"""
    name = (filename or fallback_stem).strip()
    if not name.lower().endswith(".md"):
        name = f"{name}.md"
    ascii_stem = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in name)
    if not ascii_stem or ascii_stem == ".md":
        ascii_stem = f"{fallback_stem}.md"
    elif not ascii_stem.endswith(".md"):
        ascii_stem = f"{ascii_stem.rstrip('_')}.md"
    utf8_part = quote(name, safe="")
    return f"attachment; filename=\"{ascii_stem}\"; filename*=UTF-8''{utf8_part}"
