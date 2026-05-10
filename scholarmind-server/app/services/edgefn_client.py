"""
EdgeFN OpenAI 兼容 Chat Completions（/v1/chat/completions）。
用于流式与非流式对话；兼容常见 delta 字段（含 reasoning_content）。
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.core.config import settings


def _chat_url() -> str:
    base = (settings.edgefn_api_base_url or "").strip().rstrip("/")
    return f"{base}/chat/completions"


def _extract_stream_deltas(obj: dict[str, Any]) -> tuple[str, str]:
    """从 SSE JSON 解析 (reasoning_delta, content_delta)。"""
    reasoning = ""
    content = ""
    choices = obj.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ""
    delta = choices[0].get("delta")
    if not isinstance(delta, dict):
        return "", ""
    c = delta.get("content")
    if isinstance(c, str):
        content = c
    for key in ("reasoning_content", "reasoning", "thinking"):
        r = delta.get(key)
        if isinstance(r, str):
            reasoning += r
    return reasoning, content


def _extract_message(resp_json: dict[str, Any]) -> tuple[str, str]:
    """非流式：返回 (reasoning, content)。"""
    choices = resp_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", ""
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        return "", ""
    content = msg.get("content")
    text = content if isinstance(content, str) else ""
    reasoning = ""
    for key in ("reasoning_content", "reasoning", "thinking"):
        r = msg.get(key)
        if isinstance(r, str):
            reasoning += r
    return reasoning, text


def build_chat_messages(
    user_text: str,
    *,
    deep_research: bool,
    web_search: bool,
    kb_context: str | None = None,
) -> list[dict[str, str]]:
    parts: list[str] = [
        "你是 ScholarMind 学术助手，回答简洁、可核对；优先使用 Markdown（标题、列表、代码块）。",
    ]
    if deep_research:
        parts.append("用户开启了「深度研究」：尽量分步推理并给出可验证的依据线索。")
    if web_search:
        parts.append("用户开启了「联网搜索」：若缺少实时信息请明确说明知识截止日期并避免编造链接。")
    ctx = (kb_context or "").strip()
    if ctx:
        parts.append(
            "用户已选择「知识库」。下列摘录来自其向量检索结果，请优先依据摘录作答；"
            "引用时请标明摘录序号或页码；摘录不足以回答时请明确说明，勿编造文献细节。\n\n"
            + ctx,
        )
    system = "\n\n".join(parts)
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_text},
    ]


async def complete_chat(messages: list[dict[str, str]]) -> tuple[str, str, dict[str, Any]]:
    """
    同步补全。返回 (reasoning, content, raw_json)。
    """
    key = settings.edgefn_api_key
    if not key:
        raise RuntimeError("未配置 EDGEFN_API_KEY")

    payload = {
        "model": settings.edgefn_chat_model,
        "messages": messages,
        "stream": False,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        r = await client.post(
            _chat_url(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )
        try:
            data = r.json()
        except json.JSONDecodeError as e:
            r.raise_for_status()
            raise RuntimeError(f"EdgeFN 返回非 JSON：{r.text[:500]}") from e

        if r.status_code >= 400:
            err = data.get("error") if isinstance(data, dict) else None
            if isinstance(err, dict):
                msg = err.get("message") or err.get("code") or json.dumps(err, ensure_ascii=False)
            else:
                msg = str(err or r.text[:500])
            raise RuntimeError(f"EdgeFN 错误 ({r.status_code}): {msg}")

        if not isinstance(data, dict):
            raise RuntimeError("EdgeFN 响应格式异常")
        reasoning, content = _extract_message(data)
        return reasoning, content, data


async def iter_chat_stream(messages: list[dict[str, str]]) -> AsyncIterator[tuple[str, str]]:
    """
    流式输出若干 (reasoning_delta, content_delta)，二者可同时为空（跳过）。
    """
    key = settings.edgefn_api_key
    if not key:
        raise RuntimeError("未配置 EDGEFN_API_KEY")

    payload = {
        "model": settings.edgefn_chat_model,
        "messages": messages,
        "stream": True,
    }
    async with httpx.AsyncClient(timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0)) as client:
        async with client.stream(
            "POST",
            _chat_url(),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
            },
            json=payload,
        ) as response:
            if response.status_code >= 400:
                body = await response.aread()
                text = body.decode("utf-8", errors="replace")[:2000]
                try:
                    data = json.loads(text)
                    err = data.get("error") if isinstance(data, dict) else None
                    if isinstance(err, dict):
                        msg = err.get("message") or json.dumps(err, ensure_ascii=False)
                    else:
                        msg = text
                except json.JSONDecodeError:
                    msg = text
                raise RuntimeError(f"EdgeFN 错误 ({response.status_code}): {msg}")

            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line.startswith("data:"):
                    continue
                payload_s = line[5:].strip()
                if payload_s == "[DONE]":
                    break
                try:
                    obj = json.loads(payload_s)
                except json.JSONDecodeError:
                    continue
                if not isinstance(obj, dict):
                    continue
                rs, ct = _extract_stream_deltas(obj)
                if rs or ct:
                    yield rs, ct
