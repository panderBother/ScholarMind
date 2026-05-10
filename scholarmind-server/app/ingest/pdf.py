from __future__ import annotations

from dataclasses import dataclass


@dataclass
class PageText:
    page_index: int  # 0-based
    text: str


def extract_pdf_pages(path: str) -> list[PageText]:
    import fitz  # pymupdf

    doc = fitz.open(path)
    out: list[PageText] = []
    try:
        for i in range(doc.page_count):
            page = doc.load_page(i)
            txt = page.get_text("text") or ""
            out.append(PageText(page_index=i, text=txt))
    finally:
        doc.close()
    return out
