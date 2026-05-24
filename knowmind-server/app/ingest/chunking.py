from __future__ import annotations

from dataclasses import dataclass

from app.ingest.pdf import PageText


@dataclass
class TextChunk:
    text: str
    page: int  # 0-based


def chunk_pages(
    pages: list[PageText],
    max_chars: int = 1800,
    overlap: int = 200,
) -> list[TextChunk]:
    """按页滑窗切块；后续可换论文结构感知切块。"""
    chunks: list[TextChunk] = []
    for pt in pages:
        t = (pt.text or "").strip()
        if not t:
            continue
        start = 0
        while start < len(t):
            end = min(len(t), start + max_chars)
            piece = t[start:end].strip()
            if piece:
                chunks.append(TextChunk(text=piece, page=pt.page_index))
            if end >= len(t):
                break
            start = end - overlap
    return chunks
