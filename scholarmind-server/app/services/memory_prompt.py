from __future__ import annotations

from app.core.config import get_settings
from app.core.memory_constants import approx_token_count
from app.models.orm import ChatMessage


def apply_recent_message_window(
    messages: list[ChatMessage],
    *,
    max_count: int | None = None,
    max_tokens: int | None = None,
) -> list[ChatMessage]:
    """取末尾最多 max_count 条，并从最旧开始丢直到 token 估算不超过 max_tokens。"""
    s = get_settings()
    mc = max_count if max_count is not None else s.memory_recent_message_count
    mt = max_tokens if max_tokens is not None else s.memory_recent_max_tokens
    tail = messages[-mc:] if len(messages) > mc else messages
    while tail:
        tot = sum(approx_token_count(m.content) for m in tail)
        if tot <= mt:
            break
        tail = tail[1:]
    return tail


def history_pairs_from_messages(trimmed: list[ChatMessage]) -> list[tuple[str, str]]:
    return [(m.role, m.content) for m in trimmed if m.role in ("user", "assistant")]


def retrieval_query_text(*, user_message: str, prior_assistant_tail: str | None) -> str:
    u = (user_message or "").strip()
    if prior_assistant_tail and prior_assistant_tail.strip():
        t = prior_assistant_tail.strip()
        if len(t) > 600:
            t = t[-600:]
        return f"{u}\n\n（上一轮助手回复节选）\n{t}"
    return u


def format_retrieval_hits_markdown(hits: list[dict], *, max_tokens: int | None = None) -> str:
    s = get_settings()
    budget = max_tokens if max_tokens is not None else s.memory_retrieval_max_tokens
    lines: list[str] = []
    used = 0
    for i, h in enumerate(hits, 1):
        text = str(h.get("text") or "").strip()
        if not text:
            continue
        block = f"#### 历史摘录 {i}\n{text}"
        add = approx_token_count(block)
        if used + add > budget and lines:
            break
        lines.append(block)
        used += add
    return "\n\n".join(lines)
