"""
EdgeFN OpenAI 兼容 Chat Completions（/v1/chat/completions）。
用于流式与非流式对话；兼容常见 delta 字段（含 reasoning_content）。
"""

from __future__ import annotations

import json
import re
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import Any

import httpx

from app.core.config import settings
from app.http_client import async_request_with_retry, friendly_connect_error
from app.services.file_workspace import FILE_TOOLS_SYSTEM_HINT


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


def _extract_message(resp_json: dict[str, Any]) -> tuple[str, str, list[dict[str, Any]]]:
    """非流式：返回 (reasoning, content, tool_calls)。"""
    choices = resp_json.get("choices")
    if not isinstance(choices, list) or not choices:
        return "", "", []
    msg = choices[0].get("message")
    if not isinstance(msg, dict):
        return "", "", []
    content = msg.get("content")
    text = content if isinstance(content, str) else ""
    reasoning = ""
    for key in ("reasoning_content", "reasoning", "thinking"):
        r = msg.get(key)
        if isinstance(r, str):
            reasoning += r
    tool_calls = msg.get("tool_calls")
    if not isinstance(tool_calls, list):
        tool_calls = []
    return reasoning, text, tool_calls


@dataclass
class ChatTurnResult:
    reasoning: str = ""
    content: str = ""
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)


def turn_visible_text(turn: ChatTurnResult) -> str:
    """优先 content；R1 等模型可能只有 reasoning_content。"""
    content = (turn.content or "").strip()
    if content:
        return content
    reasoning = (turn.reasoning or "").strip()
    if not reasoning:
        return ""
    text = reasoning
    for tag in ("think", "redacted_thinking", "reasoning"):
        open_pat = rf"<{tag}\b[^>]*>"
        close_pat = rf"</{tag}>"
        text = re.sub(open_pat + r"[\s\S]*?" + close_pat, "", text, flags=re.IGNORECASE)
    for tag in ("think", "redacted_thinking", "reasoning"):
        m = re.search(rf"</{tag}>\s*", text, re.IGNORECASE)
        if m:
            tail = text[m.end() :].strip()
            if tail:
                return tail
    return text.strip()


def _base_system_parts(
    *,
    deep_research: bool,
    web_search: bool,
    file_tools: bool,
) -> list[str]:
    parts: list[str] = [
        "你是 ScholarMind 学术助手，回答简洁、可核对；优先使用 Markdown（标题、列表、代码块）。",
    ]
    if deep_research:
        parts.append("用户开启了「深度研究」：尽量分步推理并给出可验证的依据线索。")
    if web_search:
        parts.append(
            "用户希望获取实时/网页信息：若 system 中已有「联网搜索结果」摘录，请优先依据摘录回答；"
            "若无摘录再说明无法核实并避免编造链接。",
        )
    if file_tools:
        parts.append(FILE_TOOLS_SYSTEM_HINT)
    return parts


def build_chat_messages(
    user_text: str,
    *,
    deep_research: bool,
    web_search: bool,
    kb_context: str | None = None,
    file_tools: bool = False,
) -> list[dict[str, str]]:
    parts = _base_system_parts(
        deep_research=deep_research,
        web_search=web_search,
        file_tools=file_tools,
    )
    ctx = (kb_context or "").strip()
    if ctx:
        if "## 联网搜索结果" in ctx:
            parts.append(
                "下列材料含知识库检索与/或联网搜索摘录。联网部分请优先用于回答网址、新闻、实时信息；"
                "知识库部分用于文献与已上传资料。摘录不足时请明确说明，勿编造。\n\n"
                + ctx,
            )
        else:
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


def build_chat_messages_multi(
    *,
    deep_research: bool,
    web_search: bool,
    file_tools: bool = False,
    kb_context: str | None,
    memory_summaries: str,
    memory_retrieval: str,
    history_pairs: list[tuple[str, str]],
) -> list[dict[str, str]]:
    """
    多轮：system 内放稳定块 A（说明+KB）+ B（摘要）+ 检索摘录；其后按序拼接 user/assistant（含当前 user）。
    """
    parts = _base_system_parts(
        deep_research=deep_research,
        web_search=web_search,
        file_tools=file_tools,
    )
    ctx = (kb_context or "").strip()
    if ctx:
        if "## 联网搜索结果" in ctx:
            parts.append(
                "下列材料含知识库检索与/或联网搜索摘录。联网部分请优先用于回答网址、新闻、实时信息；"
                "知识库部分用于文献与已上传资料。摘录不足时请明确说明，勿编造。\n\n"
                + ctx,
            )
        else:
            parts.append(
                "用户已选择「知识库」。下列摘录来自其向量检索结果，请优先依据摘录作答；"
                "引用时请标明摘录序号或页码；摘录不足以回答时请明确说明，勿编造文献细节。\n\n"
                + ctx,
            )
    summ = (memory_summaries or "").strip()
    if summ:
        parts.append("## 较早轮次摘要（系统自动生成，可能省略细节）\n\n" + summ)
    retr = (memory_retrieval or "").strip()
    if retr:
        parts.append("## 相关历史摘录（来自本会话向量检索）\n\n" + retr)
    system = "\n\n".join(parts)
    out: list[dict[str, str]] = [{"role": "system", "content": system}]
    for role, content in history_pairs:
        r = role if role in ("user", "assistant") else "user"
        out.append({"role": r, "content": content})
    return out


async def _post_chat_payload(payload: dict[str, Any]) -> dict[str, Any]:
    key = settings.edgefn_api_key
    if not key:
        raise RuntimeError("未配置 EDGEFN_API_KEY")

    chat_url = _chat_url()

    async def _do_post(client: httpx.AsyncClient) -> httpx.Response:
        return await client.post(
            chat_url,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
            json=payload,
        )

    try:
        r = await async_request_with_retry(_do_post, timeout=httpx.Timeout(180.0))
    except httpx.HTTPError as e:
        raise RuntimeError(friendly_connect_error(e)) from e

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
    return data


async def complete_chat_turn(
    messages: list[dict[str, Any]],
    *,
    tools: list[dict[str, Any]] | None = None,
) -> ChatTurnResult:
    """单轮非流式补全，可带 tools；返回正文、推理与 tool_calls。"""
    payload: dict[str, Any] = {
        "model": settings.edgefn_chat_model,
        "messages": messages,
        "stream": False,
    }
    # native 模式才传 tools；且不发送 tool_choice=auto（EdgeFN/vLLM 未开启时会 400）
    if tools:
        payload["tools"] = tools
    data = await _post_chat_payload(payload)
    reasoning, content, tool_calls = _extract_message(data)
    return ChatTurnResult(
        reasoning=reasoning,
        content=content,
        tool_calls=tool_calls,
        raw=data,
    )


async def complete_chat(messages: list[dict[str, str]]) -> tuple[str, str, dict[str, Any]]:
    """
    同步补全。返回 (reasoning, content, raw_json)。
    """
    turn = await complete_chat_turn(messages)
    return turn.reasoning, turn.content, turn.raw


def iter_text_chunks(text: str, *, chunk_size: int = 48) -> list[str]:
    """将最终正文切成小块，便于 SSE 伪流式输出。"""
    if not text:
        return []
    return [text[i : i + chunk_size] for i in range(0, len(text), chunk_size)]


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
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(connect=30.0, read=300.0, write=30.0, pool=30.0),
        trust_env=settings.http_trust_env,
    ) as client:
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
