"""解析模型正文里嵌入的工具调用（DeepSeek-R1 / Kimi 等未走 native tool_calls 时的兜底）。"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from app.services.chat_file_tools import _parse_json_object
from app.services.mcp_url_client import SEP


def _mcp_token(label: str) -> str:
    return rf"<\s*\|\s*{re.escape(label)}\s*\|\s*>"


_CALL_BEGIN = rf"(?:{_mcp_token('redacted_tool_call_begin_kimi')}|{_mcp_token('tool_call_begin')})"
_CALL_END = rf"(?:{_mcp_token('redacted_tool_call_end_kimi')}|{_mcp_token('tool_call_end')})"
_TOOL_SEP = _mcp_token("tool_sep")
_JSON_ARGS = r"(?:```(?:json)?\s*(?P<args_fence>\{[\s\S]*?\})\s*```|(?P<args_raw>\{[\s\S]*?\}))"

_CALL_BLOCK_RE = re.compile(
    rf"(?:{_mcp_token('tool_calls_begin')}\s*)?"
    rf"{_CALL_BEGIN}\s*(?:function\s*)?{_TOOL_SEP}\s*"
    rf"(?P<name>[^\s\n<`]+)"
    rf"[\s\S]*?"
    rf"{_JSON_ARGS}"
    rf"[\s\S]*?"
    rf"{_CALL_END}"
    rf"(?:\s*{_mcp_token('tool_calls_end')})?",
    re.IGNORECASE | re.DOTALL,
)

_QUALIFIED_FALLBACK_RE = re.compile(
    rf"([0-9a-fA-F-]{{8,}}{re.escape(SEP)}[\w-]+)"
    rf"[\s\S]{{0,400}}?"
    rf"{_JSON_ARGS}",
    re.DOTALL,
)

_STRIP_BLOCK_RE = re.compile(
    rf"{_mcp_token('tool_calls_begin')}[\s\S]*?{_mcp_token('tool_calls_end')}",
    re.IGNORECASE | re.DOTALL,
)
_STRIP_SINGLE_RE = re.compile(
    rf"{_CALL_BEGIN}[\s\S]*?{_CALL_END}",
    re.IGNORECASE | re.DOTALL,
)
_STRIP_MARKERS_RE = re.compile(
    rf"{_mcp_token('tool_calls_begin')}|{_mcp_token('tool_calls_end')}|{_CALL_BEGIN}|{_CALL_END}|{_TOOL_SEP}",
    re.IGNORECASE,
)


def _args_from_match(m: re.Match[str]) -> str:
    raw = m.group("args_fence") or m.group("args_raw") or "{}"
    obj = _parse_json_object(raw)
    if obj is None:
        return raw.strip()
    return json.dumps(obj, ensure_ascii=False)


def parse_text_tool_calls(
    text: str,
    *,
    known_names: set[str] | None = None,
) -> list[tuple[str, str]]:
    """从 reasoning/content 文本解析 (qualified_tool_name, arguments_json)。"""
    out: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    hay = text or ""

    def add(name: str, args: str) -> None:
        n = name.strip()
        if SEP not in n:
            return
        if known_names is not None and n not in known_names:
            return
        key = (n, args)
        if key not in seen:
            seen.add(key)
            out.append(key)

    for m in _CALL_BLOCK_RE.finditer(hay):
        add(m.group("name"), _args_from_match(m))

    if not out:
        for m in _QUALIFIED_FALLBACK_RE.finditer(hay):
            add(m.group(1), _args_from_match(m))

    return out


def strip_text_tool_calls(text: str) -> str:
    cleaned = _STRIP_BLOCK_RE.sub("", text or "")
    cleaned = _STRIP_SINGLE_RE.sub("", cleaned)
    cleaned = _STRIP_MARKERS_RE.sub("", cleaned)
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def synthetic_tool_call(name: str, arguments: str) -> dict[str, Any]:
    return {
        "id": f"call_{uuid.uuid4().hex[:12]}",
        "type": "function",
        "function": {"name": name, "arguments": arguments},
    }
