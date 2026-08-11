"""对话记忆异步后置：Chroma 写入、周期摘要（Celery 或 API 内 eager 执行）。"""

from __future__ import annotations

import asyncio
import concurrent.futures
import logging
from datetime import datetime, timezone

from sqlalchemy import func, select

from app.core.config import get_settings
from app.core.memory_constants import MEMORY_RECENT_MESSAGE_COUNT
from app.db.sync_session import session_scope
from app.indexing.chat_memory_factory import get_chat_memory_index
from app.models.orm import ChatMessage, Conversation, ConversationFact, ConversationSummary
from app.services.conversation_service import should_run_summary
from app.services.edgefn_client import build_chat_messages, complete_chat
from app.utils.llm_json import parse_llm_json_array

log = logging.getLogger(__name__)


def _sync_load_messages(session, conversation_id: str) -> list[ChatMessage]:
    q = session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc()),
    )
    return list(q.scalars().all())


def embed_last_turn_sync(
    *,
    conversation_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
    assistant_message_id: str,
) -> None:
    chunk_id = f"{conversation_id}:{assistant_message_id}"
    body = f"User:\n{user_text.strip()}\n\nAssistant:\n{assistant_text.strip()}"
    get_chat_memory_index().upsert_turn(
        chunk_id=chunk_id,
        text=body[:16000],
        conversation_id=conversation_id,
        user_id=user_id,
        chunk_kind="turn",
        assistant_message_id=assistant_message_id,
    )


def _summary_user_text(dialogue: str) -> str:
    return (
        "请将下列多轮对话压缩为结构化中文摘要，保留：主要结论、未决问题、专有名词与文档名。"
        "使用 Markdown 小标题。对话原文如下：\n\n" + dialogue[:24000]
    )


def maybe_summarize_sync(conversation_id: str) -> None:
    settings = get_settings()
    if not settings.edgefn_api_key:
        log.debug("skip summary: no EDGEFN_API_KEY")
        return

    with session_scope() as s:
        conv = s.get(Conversation, conversation_id)
        if conv is None:
            return
        prior_n = int(
            s.scalar(
                select(func.count())
                .select_from(ConversationSummary)
                .where(ConversationSummary.conversation_id == conversation_id),
            )
            or 0,
        )
        if not should_run_summary(conv, prior_summary_count=prior_n):
            return

        messages = _sync_load_messages(s, conversation_id)
        if len(messages) <= MEMORY_RECENT_MESSAGE_COUNT:
            return
        head = messages[:-MEMORY_RECENT_MESSAGE_COUNT]
        if not head:
            return
        dialogue = "\n\n".join(f"{m.role}: {m.content}" for m in head)
        covers_id = head[-1].id

    user_prompt = _summary_user_text(dialogue)
    msgs = build_chat_messages(
        user_prompt,
        deep_research=False,
        web_search=False,
        kb_context=None,
    )

    async def _call() -> tuple[str, str, dict]:
        return await complete_chat(msgs)

    try:
        _reasoning, summary_text, _raw = asyncio.run(_call())
    except Exception as e:
        log.warning("conversation summary failed: %s", e)
        return

    summary_text = (summary_text or "").strip()
    if not summary_text:
        return

    uid_for_chroma: str | None = None
    with session_scope() as s:
        conv2 = s.get(Conversation, conversation_id)
        if conv2 is None:
            return
        uid_for_chroma = conv2.user_id
        summ = ConversationSummary(
            conversation_id=conversation_id,
            covers_up_to_message_id=covers_id,
            summary_text=summary_text,
            model_version=settings.edgefn_chat_model,
        )
        s.add(summ)
        conv2.last_summarized_message_id = covers_id
        conv2.last_summary_at = datetime.now(timezone.utc)
        conv2.acc_turns_since_summary = 0
        conv2.acc_tokens_since_summary = 0

    chunk_id = f"{conversation_id}:summary:{covers_id}"
    if not uid_for_chroma:
        return
    try:
        get_chat_memory_index().upsert_turn(
            chunk_id=chunk_id,
            text=summary_text[:16000],
            conversation_id=conversation_id,
            user_id=uid_for_chroma,
            chunk_kind="summary",
            assistant_message_id=covers_id,
        )
    except Exception as e:
        log.warning("summary chroma upsert failed: %s", e)


def update_working_memory_sync(
    *,
    conversation_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
    assistant_message_id: str,
) -> None:
    """从最新一轮抽取可复用事实，并按 fact_key 更新或删除工作记忆。"""
    settings = get_settings()
    if not settings.edgefn_api_key:
        return
    prompt = (
        "从本轮对话中提取后续轮次仍有价值、且被用户明确表达或确认的工作记忆。"
        "包括用户偏好、约束、项目事实、已做决定、未决事项。不要记录临时寒暄，不要推测。"
        "如果新内容推翻旧事实，使用相同 key 和 upsert；用户明确要求忘记时使用 delete。"
        "仅输出 JSON 数组，每项格式："
        '{"key":"稳定短键","value":"事实","action":"upsert|delete","confidence":0.0}。'
        "没有事实则输出 []。\n\n"
        f"用户：{user_text[:8000]}\n\n助手：{assistant_text[:8000]}"
    )
    messages = build_chat_messages(
        prompt,
        deep_research=False,
        web_search=False,
        kb_context=None,
    )

    async def _call() -> tuple[str, str, dict]:
        return await complete_chat(messages)

    try:
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            _reasoning, content, _raw = asyncio.run(_call())
        else:
            # API 事件循环内的 eager/background 调用不能嵌套 asyncio.run；
            # 放到短生命周期线程中执行同步 LLM 提取。
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                _reasoning, content, _raw = pool.submit(lambda: asyncio.run(_call())).result()
        items = parse_llm_json_array(content) or []
    except Exception as exc:  # noqa: BLE001
        log.warning("working memory extraction failed: %s", exc)
        return

    with session_scope() as s:
        for item in items[:20]:
            if not isinstance(item, dict):
                continue
            key = str(item.get("key") or "").strip().lower()[:128]
            action = str(item.get("action") or "upsert").strip().lower()
            value = str(item.get("value") or "").strip()[:4000]
            if not key:
                continue
            existing = s.scalar(
                select(ConversationFact).where(
                    ConversationFact.conversation_id == conversation_id,
                    ConversationFact.fact_key == key,
                )
            )
            if action == "delete":
                if existing is not None:
                    s.delete(existing)
                continue
            if not value:
                continue
            try:
                confidence = max(0.0, min(1.0, float(item.get("confidence") or 0.8)))
            except (TypeError, ValueError):
                confidence = 0.8
            if existing is None:
                s.add(
                    ConversationFact(
                        conversation_id=conversation_id,
                        user_id=user_id,
                        fact_key=key,
                        fact_value=value,
                        confidence=confidence,
                        source_message_id=assistant_message_id,
                    )
                )
            else:
                existing.fact_value = value
                existing.confidence = confidence
                existing.source_message_id = assistant_message_id


def process_chat_memory_after_turn(
    *,
    conversation_id: str,
    user_id: str,
    user_text: str,
    assistant_text: str,
    assistant_message_id: str,
) -> None:
    try:
        embed_last_turn_sync(
            conversation_id=conversation_id,
            user_id=user_id,
            user_text=user_text,
            assistant_text=assistant_text,
            assistant_message_id=assistant_message_id,
        )
    except Exception as e:
        log.warning("embed chat turn failed: %s", e)
    try:
        update_working_memory_sync(
            conversation_id=conversation_id,
            user_id=user_id,
            user_text=user_text,
            assistant_text=assistant_text,
            assistant_message_id=assistant_message_id,
        )
    except Exception as e:
        log.warning("update working memory failed: %s", e)
    try:
        maybe_summarize_sync(conversation_id)
    except Exception as e:
        log.warning("maybe_summarize failed: %s", e)
