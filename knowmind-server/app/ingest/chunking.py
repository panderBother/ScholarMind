from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.ingest.types import PageText

log = logging.getLogger(__name__)

_DEFAULT_MAX_CHARS = 1800
_DEFAULT_OVERLAP = 200
_DEFAULT_MIN_CHARS = 80


@dataclass
class TextChunk:
    text: str
    page: int  # 0-based


def chunk_pages(
    pages: list[PageText],
    max_chars: int = _DEFAULT_MAX_CHARS,
    overlap: int = _DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """按页固定长度滑窗切块（兼容/回退）。"""
    chunks: list[TextChunk] = []
    for pt in pages:
        chunks.extend(chunk_text(pt.text, page=pt.page_index, max_chars=max_chars, overlap=overlap))
    return chunks


def chunk_text(
    text: str,
    *,
    page: int = 0,
    max_chars: int = _DEFAULT_MAX_CHARS,
    overlap: int = _DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """对单段文本固定长度滑窗切块。"""
    t = (text or "").strip()
    if not t:
        return []
    chunks: list[TextChunk] = []
    start = 0
    while start < len(t):
        end = min(len(t), start + max_chars)
        piece = t[start:end].strip()
        if piece:
            chunks.append(TextChunk(text=piece, page=page))
        if end >= len(t):
            break
        start = end - overlap
    return chunks


def _split_semantic_units(text: str) -> list[str]:
    """先按段落，过长段落再按句号切分为语义单元。"""
    units: list[str] = []
    for para in re.split(r"\n\s*\n+", text):
        p = para.strip()
        if not p:
            continue
        if len(p) <= 500:
            units.append(p)
            continue
        parts = re.split(r"(?<=[。！？.!?])\s*", p)
        buf = ""
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if len(buf) + len(part) <= 500:
                buf = f"{buf}{part}" if buf else part
            else:
                if buf:
                    units.append(buf)
                buf = part
        if buf:
            units.append(buf)
    return units or [text.strip()]


def _cosine(a: list[float], b: list[float]) -> float:
    import math

    dot = sum(x * y for x, y in zip(a, b, strict=True))
    na = math.sqrt(sum(x * x for x in a)) or 1e-9
    nb = math.sqrt(sum(x * x for x in b)) or 1e-9
    return dot / (na * nb)


def semantic_chunk_text(
    text: str,
    *,
    page: int = 0,
    max_chars: int = _DEFAULT_MAX_CHARS,
    min_chars: int = _DEFAULT_MIN_CHARS,
    breakpoint_percentile: float = 25.0,
) -> list[TextChunk]:
    """
    语义切块：对相邻单元做嵌入相似度，在相似度骤降处切开，再合并到 max_chars 以内。
    嵌入失败时回退为固定长度滑窗。
    """
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [TextChunk(text=t, page=page)]

    units = _split_semantic_units(t)
    if len(units) <= 1:
        return chunk_text(t, page=page, max_chars=max_chars)

    try:
        from app.ingest.embedding import embed_texts

        vectors = embed_texts([u[:4000] for u in units])
    except Exception:
        log.warning("语义切块嵌入失败，回退滑窗切块", exc_info=True)
        return chunk_text(t, page=page, max_chars=max_chars)

    breakpoints: set[int] = set()
    if len(vectors) > 1:
        sims = [_cosine(vectors[i], vectors[i + 1]) for i in range(len(vectors) - 1)]
        try:
            import numpy as np

            threshold = float(np.percentile(sims, breakpoint_percentile))
        except Exception:
            threshold = sorted(sims)[max(0, len(sims) // 4)]
        for i, sim in enumerate(sims):
            if sim <= threshold:
                breakpoints.add(i)

    chunks: list[TextChunk] = []
    buf: list[str] = []
    buflen = 0

    def flush() -> None:
        nonlocal buf, buflen
        if not buf:
            return
        joined = "\n\n".join(buf).strip()
        if joined:
            chunks.append(TextChunk(text=joined, page=page))
        buf = []
        buflen = 0

    for i, unit in enumerate(units):
        if buf and (i - 1) in breakpoints and buflen >= min_chars:
            flush()
        ulen = len(unit)
        if buf and buflen + ulen + 2 > max_chars:
            flush()
        if ulen > max_chars:
            flush()
            chunks.extend(chunk_text(unit, page=page, max_chars=max_chars))
            continue
        buf.append(unit)
        buflen += ulen + 2

    flush()
    return chunks if chunks else chunk_text(t, page=page, max_chars=max_chars)


def semantic_chunk_pages(
    pages: list[PageText],
    *,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> list[TextChunk]:
    """多页文档：按页语义切块后合并。"""
    chunks: list[TextChunk] = []
    for pt in pages:
        t = (pt.text or "").strip()
        if not t:
            continue
        chunks.extend(
            semantic_chunk_text(t, page=pt.page_index, max_chars=max_chars),
        )
    return chunks
