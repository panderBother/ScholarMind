"""MySQL TEXT 字段按 UTF-8 字节安全截断（MEDIUMTEXT 上限约 16MB）。"""

from __future__ import annotations

# 留余量，避免接近 MySQL MEDIUMTEXT 硬上限
MEDIUMTEXT_MAX_BYTES = 4_000_000


def clamp_mediumtext(text: str | None, *, max_bytes: int = MEDIUMTEXT_MAX_BYTES) -> str | None:
    if text is None:
        return None
    raw = text.encode("utf-8")
    if len(raw) <= max_bytes:
        return text
    return raw[:max_bytes].decode("utf-8", errors="ignore")
