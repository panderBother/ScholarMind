from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.memory_constants import approx_token_count
from app.models.orm import ChatMessage, Conversation, ConversationSummary, KnowledgeBase


async def get_conversation_for_user(
    session: AsyncSession,
    *,
    conversation_id: str,
    user_id: str,
) -> Conversation:
    conv = await session.get(Conversation, conversation_id)
    if conv is None or conv.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "会话不存在或无权访问")
    return conv


async def create_conversation(
    session: AsyncSession,
    *,
    user_id: str,
    knowledge_base_id: str | None,
    deep_research: bool,
    web_search: bool,
    title: str | None = None,
) -> Conversation:
    kb_ok: str | None = None
    if knowledge_base_id and str(knowledge_base_id).strip():
        kb = await session.get(KnowledgeBase, knowledge_base_id.strip())
        if kb is None or kb.user_id != user_id:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "知识库不存在或无权使用")
        kb_ok = kb.id
    conv = Conversation(
        user_id=user_id,
        knowledge_base_id=kb_ok,
        deep_research=deep_research,
        web_search=web_search,
        title=title,
    )
    session.add(conv)
    await session.flush()
    return conv


async def resolve_conversation(
    session: AsyncSession,
    *,
    user_id: str,
    conversation_id: str | None,
    knowledge_base_id: str | None,
    deep_research: bool,
    web_search: bool,
) -> tuple[Conversation, bool]:
    """
    返回 (会话, 是否本次新建)。
    conversation_id 为空则新建会话。
    """
    if conversation_id and str(conversation_id).strip():
        conv = await get_conversation_for_user(session, conversation_id=conversation_id.strip(), user_id=user_id)
        kb_ok: str | None = None
        if knowledge_base_id and str(knowledge_base_id).strip():
            kb = await session.get(KnowledgeBase, knowledge_base_id.strip())
            if kb is None or kb.user_id != user_id:
                raise HTTPException(status.HTTP_400_BAD_REQUEST, "知识库不存在或无权使用")
            kb_ok = kb.id
        conv.knowledge_base_id = kb_ok
        conv.deep_research = deep_research
        conv.web_search = web_search
        return conv, False

    conv = await create_conversation(
        session,
        user_id=user_id,
        knowledge_base_id=knowledge_base_id,
        deep_research=deep_research,
        web_search=web_search,
    )
    return conv, True


async def append_message(
    session: AsyncSession,
    *,
    conversation_id: str,
    role: str,
    content: str,
    trace_id: str | None = None,
) -> ChatMessage:
    tok = approx_token_count(content)
    m = ChatMessage(
        conversation_id=conversation_id,
        role=role,
        content=content,
        trace_id=trace_id,
        token_est=tok,
    )
    session.add(m)
    await session.flush()
    return m


async def load_messages_ordered(session: AsyncSession, conversation_id: str) -> list[ChatMessage]:
    q = await session.execute(
        select(ChatMessage)
        .where(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc()),
    )
    return list(q.scalars().all())


async def load_summaries_concat(session: AsyncSession, conversation_id: str) -> str:
    q = await session.execute(
        select(ConversationSummary)
        .where(ConversationSummary.conversation_id == conversation_id)
        .order_by(ConversationSummary.created_at.asc()),
    )
    rows = list(q.scalars().all())
    if not rows:
        return ""
    parts: list[str] = []
    for i, s in enumerate(rows, 1):
        parts.append(f"### 摘要片段 {i}\n{s.summary_text.strip()}")
    return "\n\n".join(parts)


async def count_summaries(session: AsyncSession, conversation_id: str) -> int:
    q = await session.execute(
        select(func.count()).select_from(ConversationSummary).where(
            ConversationSummary.conversation_id == conversation_id,
        ),
    )
    return int(q.scalar() or 0)


def rows_for_redis(messages: list[ChatMessage]) -> list[dict]:
    return [
        {
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "created_at": m.created_at.isoformat() if m.created_at else "",
        }
        for m in messages
    ]


def should_run_summary(conv: Conversation, *, prior_summary_count: int) -> bool:
    s = get_settings()
    vol = conv.acc_turns_since_summary >= s.memory_summary_trigger_turns or (
        conv.acc_tokens_since_summary >= s.memory_summary_trigger_tokens
    )
    if not vol:
        return False
    if prior_summary_count == 0:
        return True
    return conv.acc_turns_since_summary >= s.memory_summary_cooldown_turns or (
        conv.acc_tokens_since_summary >= s.memory_summary_cooldown_tokens
    )
