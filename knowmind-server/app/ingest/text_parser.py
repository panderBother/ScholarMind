from __future__ import annotations

from pathlib import Path

from app.ingest.types import PageText, ParseResult


def parse_text_file(path: str, filename: str | None = None, *, is_markdown: bool = False) -> ParseResult:
    raw = Path(path).read_bytes()
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb18030", "latin-1"):
        try:
            content = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            content = None
    if content is None:
        raise ValueError("无法识别文本编码")

    content = content.strip()
    base = (filename or Path(path).name).rsplit(".", 1)[0]
    title = base[:200] if base else None
    summary = None
    for line in content.splitlines():
        t = line.lstrip("#").strip()
        if t:
            summary = t[:500]
            break
    kind = "Markdown" if is_markdown else "文本"
    if not summary:
        summary = f"{kind}文件，共 {len(content)} 字"
    pages = [PageText(page_index=0, text=content)]
    return ParseResult(pages=pages, title=title, summary=summary, content=content)
