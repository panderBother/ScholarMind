import json
import uuid
from collections.abc import AsyncIterator

from app.core.config import settings
from app.models.schemas import ChatRequest, ChatResponse
from app.services.edgefn_client import build_chat_messages, complete_chat, iter_chat_stream as iter_edgefn_token_stream


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


async def iter_chat_stream(req: ChatRequest, *, kb_context: str = "") -> AsyncIterator[str]:
    """
    SSE：`trace_id` → 可选 `thinking_delta` / `delta` → `done`。
    正文来自 EdgeFN 流式接口；思维链字段随服务商 delta（如 reasoning_content）推送。
    """
    trace_id = str(uuid.uuid4())
    yield _sse_event({"type": "trace_id", "trace_id": trace_id})

    if not settings.edgefn_api_key:
        yield _sse_event(
            {
                "type": "error",
                "message": "未配置 EDGEFN_API_KEY：请在 scholarmind-server/.env 中设置第三方密钥后重启服务。",
            },
        )
        yield _sse_event({"type": "done"})
        return

    messages = build_chat_messages(
        req.message,
        deep_research=req.deep_research,
        web_search=req.web_search,
        kb_context=kb_context or None,
    )

    try:
        async for reasoning_piece, content_piece in iter_edgefn_token_stream(messages):
            if reasoning_piece:
                yield _sse_event({"type": "thinking_delta", "text": reasoning_piece})
            if content_piece:
                yield _sse_event({"type": "delta", "text": content_piece})
    except RuntimeError as e:
        yield _sse_event({"type": "error", "message": str(e)})
    except Exception as e:  # noqa: BLE001 — 向前端返回可读错误
        yield _sse_event({"type": "error", "message": f"对话上游异常：{e!s}"})

    yield _sse_event({"type": "done"})


async def run_chat(req: ChatRequest, *, kb_context: str = "") -> ChatResponse:
    """同步 JSON：一次性返回模型正文（含可选推理过程，前置在 reply 中）。"""
    trace_id = str(uuid.uuid4())

    if not settings.edgefn_api_key:
        return ChatResponse(
            reply="（配置缺失）请在服务器环境变量 EDGEFN_API_KEY 中填写 EdgeFN 密钥并重启 API。",
            trace_id=trace_id,
        )

    messages = build_chat_messages(
        req.message,
        deep_research=req.deep_research,
        web_search=req.web_search,
        kb_context=kb_context or None,
    )
    try:
        reasoning, content, _raw = await complete_chat(messages)
    except RuntimeError as e:
        return ChatResponse(reply=f"（调用失败）{e}", trace_id=trace_id)
    except Exception as e:  # noqa: BLE001
        return ChatResponse(reply=f"（调用失败）{e!s}", trace_id=trace_id)

    parts: list[str] = []
    if reasoning.strip():
        parts.append(reasoning.strip())
        parts.append("\n\n---\n\n")
    parts.append(content if content.strip() else "（模型返回空正文）")
    return ChatResponse(reply="".join(parts), trace_id=trace_id)
