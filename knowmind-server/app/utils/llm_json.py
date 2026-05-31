"""从 LLM 正文中提取 JSON 数组（忽略字符串内的括号）。"""

from __future__ import annotations

import json
import re
from typing import Any


def _strip_markdown_fence(text: str) -> str:
    s = text.strip()
    if s.startswith("```"):
        s = re.sub(r"^```(?:json)?\s*", "", s, count=1, flags=re.IGNORECASE)
        s = re.sub(r"\s*```\s*$", "", s)
    return s.strip()


def parse_llm_json_array(raw: str) -> list[Any] | None:
    """
    从模型输出中解析第一个完整的 JSON 数组。
    避免贪婪正则误匹配 content 里的 ] 或数组后的多余文本。
    """
    text = _strip_markdown_fence(raw or "")
    if not text:
        return None
    start = text.find("[")
    if start < 0:
        return None
    depth = 0
    in_str = False
    escape = False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
            continue
        if ch == "[":
            depth += 1
        elif ch == "]":
            depth -= 1
            if depth == 0:
                try:
                    obj = json.loads(text[start : i + 1])
                except json.JSONDecodeError:
                    return None
                return obj if isinstance(obj, list) else None
    return None
