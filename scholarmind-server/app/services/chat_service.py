import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.memory_constants import approx_token_count
from app.indexing.chat_memory_factory import get_chat_memory_index
from app.ingest.embedding import embed_texts
from app.models.orm import ChatMessage, Conversation
from app.models.schemas import ChatRequest, ChatResponse
from app.services.conversation_service import (
    append_message,
    load_messages_ordered,
    load_summaries_concat,
    resolve_conversation,
    rows_for_redis,
)
from app.services.edgefn_client import (
    build_chat_messages,
    build_chat_messages_multi,
    complete_chat,
    iter_chat_stream as iter_edgefn_token_stream,
)
from app.services.memory_prompt import (
    apply_recent_message_window,
    format_retrieval_hits_markdown,
    history_pairs_from_messages,
    retrieval_query_text,
)
from app.services.redis_conv import set_recent_messages


def _sse_event(payload: dict) -> str:
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _enqueue_chat_memory(
    *,
    conversation_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
    assistant_message_id: str,
) -> None:
    try:
        from app.workers.memory_tasks import process_chat_memory_after_turn_task

        process_chat_memory_after_turn_task.delay(
            conversation_id=conversation_id,
            user_id=user_id,
            user_text=user_text,
            assistant_text=assistant_text,
            assistant_message_id=assistant_message_id,
        )
    except Exception:
        from app.services.chat_memory_worker import process_chat_memory_after_turn

        process_chat_memory_after_turn(
            conversation_id=conversation_id,
            user_id=user_id,
            user_text=user_text,
            assistant_text=assistant_text,
            assistant_message_id=assistant_message_id,
        )


async def iter_chat_stream(
    req: ChatRequest,
    *,
    kb_context: str = "",
    session: AsyncSession | None = None,
    user_id: str | None = None,
) -> AsyncIterator[str]:
    """
    SSE：`trace_id` → `conversation_id`（多轮）→ 可选 `thinking_delta` / `delta` → `done`。
    若传入 session + user_id，则启用 MySQL 会话、Redis 热数据与对话向量检索组装多轮 prompt。
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

    use_memory = session is not None and user_id is not None

    if not use_memory:
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
        except Exception as e:  # noqa: BLE001
            yield _sse_event({"type": "error", "message": f"对话上游异常：{e!s}"})
        yield _sse_event({"type": "done"})
        return

    conv, is_new = await resolve_conversation(
        session,
        user_id=user_id,
        conversation_id=req.conversation_id,
        knowledge_base_id=req.knowledge_base_id,
        deep_research=req.deep_research,
        web_search=req.web_search,
    )
    yield _sse_event({"type": "conversation_id", "conversation_id": conv.id, "is_new": is_new})

    user_row = await append_message(
        session,
        conversation_id=conv.id,
        role="user",
        content=req.message.strip(),
        trace_id=None,
    )
    await session.flush()
    n_user = await session.scalar(
        select(func.count()).select_from(ChatMessage).where(
            ChatMessage.conversation_id == conv.id,
            ChatMessage.role == "user",
        ),
    )
    if n_user == 1:
        conv_row = await session.get(Conversation, conv.id)
        if conv_row is not None and not (conv_row.title and str(conv_row.title).strip()):
            raw = req.message.strip().replace("\n", " ")
            conv_row.title = raw[:80] + ("…" if len(raw) > 80 else "")
    await session.commit()
    await session.refresh(user_row)

    all_msgs = await load_messages_ordered(session, conv.id)
    prior_assistant_tail: str | None = None
    for m in reversed(all_msgs[:-1]):
        if m.role == "assistant":
            prior_assistant_tail = m.content
            break

    qtext = retrieval_query_text(user_message=req.message, prior_assistant_tail=prior_assistant_tail)
    summaries = await load_summaries_concat(session, conv.id)

    retrieval_md = ""
    try:
        q_vectors = await asyncio.to_thread(embed_texts, [qtext[:8000]])
        qvec = q_vectors[0]
        hits = await asyncio.to_thread(
            get_chat_memory_index().query_for_conversation,
            conversation_id=conv.id,
            user_id=user_id,
            query_embedding=qvec,
            top_k=settings.memory_retrieval_top_k,
        )
        retrieval_md = format_retrieval_hits_markdown(hits)
    except Exception:
        retrieval_md = ""

    trimmed = apply_recent_message_window(all_msgs)
    pairs = history_pairs_from_messages(trimmed)
    messages = build_chat_messages_multi(
        deep_research=req.deep_research,
        web_search=req.web_search,
        kb_context=kb_context or None,
        memory_summaries=summaries,
        memory_retrieval=retrieval_md,
        history_pairs=pairs,
    )

    assistant_body_parts: list[str] = []
    stream_ok = False
    try:
        async for reasoning_piece, content_piece in iter_edgefn_token_stream(messages):
            if reasoning_piece:
                yield _sse_event({"type": "thinking_delta", "text": reasoning_piece})
            if content_piece:
                assistant_body_parts.append(content_piece)
                yield _sse_event({"type": "delta", "text": content_piece})
        stream_ok = True
    except RuntimeError as e:
        yield _sse_event({"type": "error", "message": str(e)})
    except Exception as e:  # noqa: BLE001
        yield _sse_event({"type": "error", "message": f"对话上游异常：{e!s}"})

    if stream_ok:
        assistant_text = "".join(assistant_body_parts).strip() or "（模型返回空正文）"
        asst_row = await append_message(
            session,
            conversation_id=conv.id,
            role="assistant",
            content=assistant_text,
            trace_id=trace_id,
        )
        conv_ref = await session.get(Conversation, conv.id)
        if conv_ref is not None:
            ut = int(user_row.token_est or approx_token_count(user_row.content))
            at = approx_token_count(assistant_text)
            conv_ref.acc_turns_since_summary = int(conv_ref.acc_turns_since_summary or 0) + 1
            conv_ref.acc_tokens_since_summary = int(conv_ref.acc_tokens_since_summary or 0) + ut + at
            conv_ref.updated_at = datetime.now(timezone.utc)
        await session.commit()
        await session.refresh(asst_row)

        full = await load_messages_ordered(session, conv.id)
        await set_recent_messages(conv.id, rows_for_redis(full))

        _enqueue_chat_memory(
            conversation_id=conv.id,
            user_id=user_id,
            user_text=user_row.content,
            assistant_text=assistant_text,
            assistant_message_id=asst_row.id,
        )

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
