from fastapi import APIRouter, Depends, status
from starlette.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.models.orm import Conversation
from app.schemas.conversation import ChatMessageOut, ConversationCreate, ConversationOut
from app.services.conversation_service import create_conversation, get_conversation_for_user, load_messages_ordered

router = APIRouter()


@router.post("", response_model=ConversationOut)
async def create_conversation_endpoint(
    body: ConversationCreate,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    conv = await create_conversation(
        session,
        user_id=user_id,
        knowledge_base_id=body.knowledge_base_id,
        deep_research=body.deep_research,
        web_search=body.web_search,
        title=body.title,
    )
    await session.commit()
    await session.refresh(conv)
    return conv


@router.get("", response_model=list[ConversationOut])
async def list_conversations(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    limit: int = 50,
):
    lim = max(1, min(limit, 100))
    q = await session.execute(
        select(Conversation)
        .where(Conversation.user_id == user_id)
        .order_by(Conversation.updated_at.desc())
        .limit(lim),
    )
    return list(q.scalars().all())


@router.get("/{conversation_id}/messages", response_model=list[ChatMessageOut])
async def list_messages(
    conversation_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    await get_conversation_for_user(session, conversation_id=conversation_id, user_id=user_id)
    rows = await load_messages_ordered(session, conversation_id)
    return rows


@router.get("/{conversation_id}", response_model=ConversationOut)
async def get_conversation_endpoint(
    conversation_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    """刷新前端恢复会话时拉取元数据（含 knowledge_base_id）。"""
    conv = await get_conversation_for_user(session, conversation_id=conversation_id, user_id=user_id)
    return conv


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_conversation(
    conversation_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    conv = await get_conversation_for_user(session, conversation_id=conversation_id, user_id=user_id)
    await session.delete(conv)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
