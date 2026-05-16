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
from app.core.logging_setup import log_info
from app.services.chat_file_tools import (
    ToolTraceEntry,
    all_user_texts,
    build_messages_for_file_task,
    build_write_calls,
    complete_chat_with_file_tools,
    execute_tool_calls,
    has_read_intent,
    has_write_intent,
    try_direct_write_from_user_message,
    try_read_files_from_user_texts,
)
from app.services.edgefn_client import complete_chat_turn
from app.services.file_tool_logging import tool_log_message
from app.services.edgefn_client import (
    build_chat_messages,
    build_chat_messages_multi,
    complete_chat,
    iter_chat_stream as iter_edgefn_token_stream,
    iter_text_chunks,
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


def _want_file_tools(req: ChatRequest, user_id: str | None = None) -> bool:
    if not settings.file_tools_enabled or not req.file_tools:
        return False
    if user_id:
        from app.services import mcp_registry

        return mcp_registry.is_builtin_enabled(user_id, "file_writer")
    return True


def _message_suggests_web_search(message: str) -> bool:
    from web_search.operations import extract_urls

    text = (message or "").strip()
    if not text:
        return False
    if extract_urls(text):
        return True
    hints = ("最新", "今天", "新闻", "股价", "天气", "官网", "网站", "链接", "http")
    return any(h in text for h in hints)


def _want_web_search(req: ChatRequest, user_id: str | None = None) -> bool:
    if not settings.web_search_enabled:
        return False
    if user_id:
        from app.services import mcp_registry

        if not mcp_registry.is_builtin_enabled(user_id, "web_search"):
            return False
    # 对话开关 或 工具页已启用且消息含 URL/实时意图（避免旧会话 web_search=false 导致完全不搜）
    if req.web_search:
        return True
    if user_id:
        from app.services import mcp_registry

        if mcp_registry.is_builtin_enabled(user_id, "web_search") and _message_suggests_web_search(
            req.message,
        ):
            return True
    return False


async def _merge_web_search_context(
    req: ChatRequest,
    kb_context: str,
    user_id: str | None = None,
) -> tuple[str, bool]:
    """返回 (合并后的上下文, 是否已注入联网块（含「无结果」说明）)。"""
    if not _want_web_search(req, user_id):
        if settings.web_search_enabled and req.web_search and user_id:
            from app.services import mcp_registry

            if not mcp_registry.is_builtin_enabled(user_id, "web_search"):
                log_info("[web_search] 跳过：请在「工具与集成」中开启 Web Search")
        elif settings.web_search_enabled and not req.web_search and not _message_suggests_web_search(
            req.message,
        ):
            log_info("[web_search] 跳过：对话未开启「联网搜索」开关")
        return kb_context, False
    from app.services.web_search_service import fetch_web_context_markdown

    auto = not req.web_search and _message_suggests_web_search(req.message)
    if auto:
        log_info("[web_search] 自动检索（消息含链接/实时意图，MCP 已启用）")
    web_md = await fetch_web_context_markdown(req.message)
    if not web_md.strip():
        return kb_context, False
    parts = [p for p in (kb_context, web_md) if p and p.strip()]
    return "\n\n".join(parts), True


def _tool_trace_sse(entry: ToolTraceEntry) -> dict:
    return {
        "type": "tool_result",
        "tool": entry.name,
        "ok": entry.ok,
        "result": entry.result,
    }


def _file_log_sse(message: str) -> dict:
    return {"type": "file_log", "message": message}


def _emit_tool_events(entry: ToolTraceEntry) -> list[dict]:
    """仅推送工具结果；失败提示只写服务端日志，不在对话里显示绿框。"""
    if not entry.ok:
        log_info("[file_tools] %s", tool_log_message(entry))
        return []
    return [_tool_trace_sse(entry)]


def _has_write_trace(traces: list[ToolTraceEntry]) -> bool:
    return any(t.name in ("write_document", "write_markdown") and t.ok for t in traces)


def _file_tools_noop_hint(req: ChatRequest) -> str:
    msg = req.message.strip()
    if has_read_intent(msg):
        return (
            "未读取到文件：请写清路径，例如 "
            "E:\\velochat\\项目聊天.md 或「E盘里的 velochat项目聊天.md」"
        )
    if has_write_intent(msg):
        return "未执行文件写入：请在同一条消息里写清路径（如 D:\\test\\a.md）和要保存的正文"
    return "未执行文件操作"


async def _stream_file_tools_turn(
    req: ChatRequest,
    messages: list,
    *,
    kb_context: str = "",
) -> tuple[str, str, list[ToolTraceEntry]]:
    """读取/写入本地文件 + 必要时再调模型（含读文件后总结）。"""
    traces: list[ToolTraceEntry] = []
    user_texts = [req.message.strip(), *all_user_texts(messages)]
    seen_u: set[str] = set()
    unique_user_texts: list[str] = []
    for t in user_texts:
        if t and t not in seen_u:
            seen_u.add(t)
            unique_user_texts.append(t)

    user_blob = "\n\n".join(unique_user_texts)
    if has_read_intent(user_blob):
        read_traces, file_body, file_path = try_read_files_from_user_texts(unique_user_texts)
        traces.extend(read_traces)
        if file_body and file_path:
            log_info("[file_tools] 读文件后生成回复 path=%s", file_path)
            summary_messages = build_messages_for_file_task(
                req.message,
                file_path,
                file_body,
                kb_context=kb_context or None,
            )
            turn = await complete_chat_turn(summary_messages)
            return turn.reasoning, turn.content, traces

    direct = try_direct_write_from_user_message(req.message.strip())
    if direct:
        traces.append(direct)

    async def on_tool(entry: ToolTraceEntry) -> None:
        traces.append(entry)

    result = await complete_chat_with_file_tools(messages, on_tool=on_tool)
    seen = {(t.name, t.arguments) for t in traces}
    for t in result.tool_traces:
        key = (t.name, t.arguments)
        if key not in seen:
            traces.append(t)
            seen.add(key)

    if not _has_write_trace(traces):
        post_calls = build_write_calls(unique_user_texts, result.content)
        if post_calls:
            log_info("[file_tools] 模型回复后备用写入 calls=%s", len(post_calls))
            traces.extend(execute_tool_calls(post_calls))

    return result.reasoning, result.content, traces


def _yield_traces(traces: list[ToolTraceEntry]) -> list[dict]:
    events: list[dict] = []
    for entry in traces:
        events.extend(_emit_tool_events(entry))
    return events


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
    merged_kb, web_injected = await _merge_web_search_context(req, kb_context, user_id)
    web_hint = _want_web_search(req, user_id) and not web_injected

    if not use_memory:
        messages = build_chat_messages(
            req.message,
            deep_research=req.deep_research,
            web_search=web_hint,
            kb_context=merged_kb or None,
            file_tools=_want_file_tools(req, user_id),
        )
        try:
            if _want_file_tools(req, user_id):
                log_info("[file_tools] chat/stream 已启用 file_tools")
                reasoning, content, traces = await _stream_file_tools_turn(
                    req, messages, kb_context=merged_kb or "",
                )
                for ev in _yield_traces(traces):
                    yield _sse_event(ev)
                if not traces:
                    log_info("[file_tools] %s", _file_tools_noop_hint(req))
                if reasoning.strip():
                    for chunk in iter_text_chunks(reasoning):
                        yield _sse_event({"type": "thinking_delta", "text": chunk})
                for chunk in iter_text_chunks(content or "（模型返回空正文）"):
                    yield _sse_event({"type": "delta", "text": chunk})
            else:
                if web_injected:
                    log_info("[web_search] chat/stream 已注入联网结果")
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
        web_search=web_hint,
        file_tools=_want_file_tools(req, user_id),
        kb_context=merged_kb or None,
        memory_summaries=summaries,
        memory_retrieval=retrieval_md,
        history_pairs=pairs,
    )

    assistant_body_parts: list[str] = []
    stream_ok = False
    try:
        if _want_file_tools(req, user_id):
            log_info("[file_tools] chat/stream(多轮) 已启用 file_tools")
            reasoning, content, traces = await _stream_file_tools_turn(
                req, messages, kb_context=merged_kb or "",
            )
            for ev in _yield_traces(traces):
                yield _sse_event(ev)
            if not traces:
                log_info("[file_tools] %s", _file_tools_noop_hint(req))
            if reasoning.strip():
                for chunk in iter_text_chunks(reasoning):
                    yield _sse_event({"type": "thinking_delta", "text": chunk})
            body = content or "（模型返回空正文）"
            assistant_body_parts.append(body)
            for chunk in iter_text_chunks(body):
                yield _sse_event({"type": "delta", "text": chunk})
            stream_ok = True
        else:
            if web_injected:
                log_info("[web_search] chat/stream(多轮) 已注入联网结果")
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

    merged_kb, web_injected = await _merge_web_search_context(req, kb_context, None)
    web_hint = _want_web_search(req, None) and not web_injected
    messages = build_chat_messages(
        req.message,
        deep_research=req.deep_research,
        web_search=web_hint,
        kb_context=merged_kb or None,
        file_tools=_want_file_tools(req),
    )
    try:
        if _want_file_tools(req):
            reasoning, content, _traces = await _stream_file_tools_turn(
                req, messages, kb_context=merged_kb or "",
            )
        else:
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
