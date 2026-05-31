"""同步对话：复用 iter_chat_stream 的 SSE 输出，避免与流式行为分叉。"""

from __future__ import annotations

import json

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session_factory
from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_service import iter_chat_stream


def _parse_sse_line(line: str) -> dict | None:
    if not line.startswith("data:"):
        return None
    raw = line[5:].strip()
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None


async def collect_chat_response(
    req: ChatRequest,
    *,
    session: AsyncSession | None = None,
    user_id: str | None = None,
    expert_prompt: str | None = None,
) -> ChatResponse:
    trace_id = ""
    deltas: list[str] = []
    thinking: list[str] = []
    errors: list[str] = []

    async def _consume(sess: AsyncSession, uid: str | None) -> None:
        nonlocal trace_id
        async for line in iter_chat_stream(
            req,
            session=sess,
            user_id=uid,
            expert_prompt=expert_prompt,
        ):
            for part in line.split("\n"):
                msg = _parse_sse_line(part.strip())
                if not msg:
                    continue
                t = msg.get("type")
                if t == "trace_id" and isinstance(msg.get("trace_id"), str):
                    trace_id = msg["trace_id"]
                elif t == "delta" and isinstance(msg.get("text"), str):
                    deltas.append(msg["text"])
                elif t == "thinking_delta" and isinstance(msg.get("text"), str):
                    thinking.append(msg["text"])
                elif t == "error" and isinstance(msg.get("message"), str):
                    errors.append(msg["message"])

    if session is not None and user_id is not None:
        await _consume(session, user_id)
    else:
        factory = get_session_factory()
        async with factory() as sess:
            await _consume(sess, user_id)

    if errors and not deltas:
        return ChatResponse(reply=f"（调用失败）{errors[-1]}", trace_id=trace_id or "sync")

    body = "".join(deltas).strip()
    if thinking and not body:
        body = "".join(thinking).strip()
    if not body:
        body = "（模型返回空正文）"
    return ChatResponse(reply=body, trace_id=trace_id or "sync")
