"""将研究报告 Markdown 导出为 PDF（PyMuPDF HTML 渲染）。"""

from __future__ import annotations

import html
import re

import fitz  # pymupdf


def _md_to_html(title: str, body_md: str) -> str:
    text = body_md or ""
    lines = text.splitlines()
    parts: list[str] = [
        "<html><head><meta charset='utf-8'>",
        "<style>body{font-family:sans-serif;font-size:11pt;line-height:1.5;padding:12px;}"
        "h1{font-size:18pt;}h2{font-size:14pt;}h3{font-size:12pt;}pre,code{font-size:10pt;}</style>",
        "</head><body>",
        f"<h1>{html.escape(title)}</h1>",
    ]
    in_code = False
    code_buf: list[str] = []
    for line in lines:
        if line.strip().startswith("```"):
            if in_code:
                parts.append(f"<pre>{html.escape(chr(10).join(code_buf))}</pre>")
                code_buf = []
                in_code = False
            else:
                in_code = True
            continue
        if in_code:
            code_buf.append(line)
            continue
        if line.startswith("### "):
            parts.append(f"<h3>{html.escape(line[4:].strip())}</h3>")
        elif line.startswith("## "):
            parts.append(f"<h2>{html.escape(line[3:].strip())}</h2>")
        elif line.startswith("# "):
            parts.append(f"<h2>{html.escape(line[2:].strip())}</h2>")
        elif re.match(r"^[-*]\s+", line):
            item_text = re.sub(r"^[-*]\s+", "", line)
            parts.append(f"<li>{html.escape(item_text)}</li>")
        elif not line.strip():
            parts.append("<br/>")
        else:
            parts.append(f"<p>{html.escape(line)}</p>")
    if in_code and code_buf:
        parts.append(f"<pre>{html.escape(chr(10).join(code_buf))}</pre>")
    parts.append("</body></html>")
    return "\n".join(parts)


def markdown_to_pdf_bytes(*, title: str, markdown: str) -> bytes:
    html_doc = _md_to_html(title, markdown)
    doc = fitz.open()
    page = doc.new_page(width=595, height=842)  # A4
    rect = fitz.Rect(40, 40, 555, 802)
    page.insert_htmlbox(rect, html_doc)
    return doc.tobytes()
