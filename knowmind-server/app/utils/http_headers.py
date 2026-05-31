from __future__ import annotations

from urllib.parse import quote


def attachment_content_disposition(filename: str, *, fallback_stem: str = "report") -> str:
    """Content-Disposition 支持中文文件名（RFC 5987），避免 latin-1 编码错误。"""
    name = (filename or fallback_stem).strip()
    lower = name.lower()
    if not (lower.endswith(".md") or lower.endswith(".pdf")):
        name = f"{name}.md"
    ext = ".pdf" if lower.endswith(".pdf") else ".md"
    ascii_stem = "".join(c if c.isascii() and (c.isalnum() or c in "._-") else "_" for c in name)
    if not ascii_stem or ascii_stem == ext:
        ascii_stem = f"{fallback_stem}{ext}"
    elif not ascii_stem.lower().endswith(ext):
        ascii_stem = f"{ascii_stem.rstrip('_')}{ext}"
    utf8_part = quote(name, safe="")
    return f"attachment; filename=\"{ascii_stem}\"; filename*=UTF-8''{utf8_part}"
