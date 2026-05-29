from __future__ import annotations

from pathlib import Path

from app.ingest.types import PageText, ParseResult


def _cell_text(cell) -> str:
    return (cell.text or "").strip()


def _table_to_markdown(table) -> str:
    rows: list[list[str]] = []
    for row in table.rows:
        cells = [_cell_text(c) for c in row.cells]
        if any(cells):
            rows.append(cells)
    if not rows:
        return ""
    col_count = max(len(r) for r in rows)
    normalized = [r + [""] * (col_count - len(r)) for r in rows]
    lines: list[str] = []
    for i, row in enumerate(normalized):
        line = "| " + " | ".join(c.replace("|", "\\|") for c in row) + " |"
        lines.append(line)
        if i == 0:
            lines.append("| " + " | ".join("---" for _ in row) + " |")
    return "\n".join(lines)


def _heading_level(style_name: str | None) -> int | None:
    if not style_name:
        return None
    name = style_name.lower()
    if name.startswith("heading"):
        try:
            return int(name.replace("heading", "").strip() or "1")
        except ValueError:
            return 1
    if "标题" in style_name:
        for n in range(1, 7):
            if str(n) in style_name:
                return n
        return 1
    return None


def parse_docx(path: str, filename: str | None = None) -> ParseResult:
    from docx import Document as DocxDocument  # noqa: PLC0415
    from docx.table import Table  # noqa: PLC0415
    from docx.text.paragraph import Paragraph  # noqa: PLC0415

    doc = DocxDocument(path)
    blocks: list[str] = []
    body = doc.element.body
    para_idx = 0
    table_idx = 0

    for child in body.iterchildren():
        tag = child.tag.split("}")[-1]
        if tag == "p":
            if para_idx >= len(doc.paragraphs):
                continue
            para: Paragraph = doc.paragraphs[para_idx]
            para_idx += 1
            text = (para.text or "").strip()
            if not text:
                continue
            level = _heading_level(para.style.name if para.style else None)
            if level:
                blocks.append(f"{'#' * level} {text}")
            else:
                blocks.append(text)
        elif tag == "tbl":
            if table_idx >= len(doc.tables):
                continue
            table: Table = doc.tables[table_idx]
            table_idx += 1
            md = _table_to_markdown(table)
            if md:
                blocks.append(md)

    content = "\n\n".join(blocks)
    base = (filename or Path(path).name).rsplit(".", 1)[0]
    title = base[:200] if base else None
    summary = None
    for block in blocks:
        t = block.lstrip("#").strip()
        if t:
            summary = t[:500]
            break
    pages = [PageText(page_index=0, text=content)] if content else []
    return ParseResult(pages=pages, title=title, summary=summary, content=content)


def parse_doc(path: str, filename: str | None = None) -> ParseResult:
    """旧版 .doc：尝试 olefile 提取，失败则提示转换。"""
    try:
        import olefile  # noqa: PLC0415

        if not olefile.isOleFile(path):
            raise ValueError("不是有效的 Word .doc 文件")
        ole = olefile.OleFileIO(path)
        try:
            if ole.exists("WordDocument"):
                # 仅能粗略提取可见 ASCII/Unicode，复杂格式请转 DOCX
                data = ole.openstream("WordDocument").read()
                text_parts: list[str] = []
                chunk = data.decode("utf-16-le", errors="ignore")
                for line in chunk.split("\x00"):
                    t = line.strip()
                    if len(t) >= 2 and any(c.isalnum() or "\u4e00" <= c <= "\u9fff" for c in t):
                        text_parts.append(t)
                content = "\n\n".join(dict.fromkeys(text_parts))[:50000]
                if len(content) >= 20:
                    base = (filename or Path(path).name).rsplit(".", 1)[0]
                    return ParseResult(
                        pages=[PageText(page_index=0, text=content)],
                        title=base[:200],
                        summary=content[:500],
                        content=content,
                    )
        finally:
            ole.close()
    except ImportError:
        pass
    except Exception:
        pass
    raise ValueError("无法解析 .doc 文件，请另存为 .docx 后重新上传")
