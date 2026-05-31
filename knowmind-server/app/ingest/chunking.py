from __future__ import annotations

import logging
import re
from dataclasses import dataclass

from app.ingest.types import PageText

log = logging.getLogger(__name__)

_DEFAULT_MAX_CHARS = 640
_DEFAULT_MIN_CHARS = 120
_DEFAULT_OVERLAP = 100


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


def _pack_units(
    units: list[str],
    *,
    min_chars: int,
    max_chars: int,
    page: int,
    overlap: int,
) -> list[TextChunk]:
    """
    按语义单元打包：仅将 < min_chars 的碎片与相邻合并；单块不超过 max_chars，不凑满大块。
    """
    chunks: list[TextChunk] = []
    buf = ""

    def flush_buffer() -> None:
        nonlocal buf
        piece = buf.strip()
        if piece:
            chunks.append(TextChunk(text=piece, page=page))
        buf = ""

    for unit in units:
        u = unit.strip()
        if not u:
            continue
        if len(u) > max_chars:
            flush_buffer()
            chunks.extend(chunk_text(u, page=page, max_chars=max_chars, overlap=overlap))
            continue
        candidate = f"{buf}\n\n{u}" if buf else u
        if len(candidate) > max_chars:
            flush_buffer()
            buf = u
        else:
            buf = candidate
        if len(buf) >= min_chars:
            flush_buffer()

    tail = buf.strip()
    if tail:
        if chunks and len(tail) < min_chars:
            merged = f"{chunks[-1].text}\n\n{tail}"
            if len(merged) <= max_chars:
                chunks[-1] = TextChunk(text=merged, page=page)
            else:
                chunks.append(TextChunk(text=tail, page=page))
        else:
            chunks.append(TextChunk(text=tail, page=page))

    return chunks


def semantic_chunk_text(
    text: str,
    *,
    page: int = 0,
    max_chars: int = _DEFAULT_MAX_CHARS,
    min_chars: int = _DEFAULT_MIN_CHARS,
    overlap: int = _DEFAULT_OVERLAP,
    breakpoint_percentile: float = 25.0,  # noqa: ARG001 — 保留签名兼容
) -> list[TextChunk]:
    """
    语义切块：段落/句号切分 → 仅对 < min_chars 轻量合并 → 单块上限 max_chars。
    不再按嵌入相似度合并到超大块。
    """
    t = (text or "").strip()
    if not t:
        return []
    if len(t) <= max_chars:
        return [TextChunk(text=t, page=page)]

    units = _split_semantic_units(t)
    if len(units) <= 1:
        return chunk_text(t, page=page, max_chars=max_chars, overlap=overlap)

    packed = _pack_units(
        units,
        min_chars=min_chars,
        max_chars=max_chars,
        page=page,
        overlap=overlap,
    )
    return packed if packed else chunk_text(t, page=page, max_chars=max_chars, overlap=overlap)


def semantic_chunk_pages(
    pages: list[PageText],
    *,
    max_chars: int = _DEFAULT_MAX_CHARS,
    min_chars: int = _DEFAULT_MIN_CHARS,
    overlap: int = _DEFAULT_OVERLAP,
) -> list[TextChunk]:
    """多页文档：按页语义切块。"""
    chunks: list[TextChunk] = []
    for pt in pages:
        t = (pt.text or "").strip()
        if not t:
            continue
        chunks.extend(
            semantic_chunk_text(
                t,
                page=pt.page_index,
                max_chars=max_chars,
                min_chars=min_chars,
                overlap=overlap,
            ),
        )
    return chunks


def chunk_settings_from_config() -> tuple[int, int, int]:
    """从运行时配置读取切块参数。"""
    from app.core.config import get_settings

    s = get_settings()
    return (
        int(s.chunk_min_chars),
        int(s.chunk_max_chars),
        int(s.chunk_overlap),
    )
