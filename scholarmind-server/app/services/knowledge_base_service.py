from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.orm import KnowledgeBase, new_uuid


class KnowledgeBaseError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def count_by_user(session: AsyncSession, user_id: str) -> int:
    q = select(func.count()).select_from(KnowledgeBase).where(KnowledgeBase.user_id == user_id)
    r = await session.execute(q)
    return int(r.scalar_one())


async def list_knowledge_bases(session: AsyncSession, user_id: str) -> list[KnowledgeBase]:
    q = (
        select(KnowledgeBase)
        .where(KnowledgeBase.user_id == user_id)
        .order_by(KnowledgeBase.updated_at.desc())
    )
    r = await session.execute(q)
    return list(r.scalars().all())


async def create_knowledge_base(session: AsyncSession, user_id: str, name: str) -> KnowledgeBase:
    name = name.strip()
    if not name:
        raise KnowledgeBaseError("知识库名称不能为空", 400)

    n = await count_by_user(session, user_id)
    if n >= settings.max_knowledge_bases_per_user:
        raise KnowledgeBaseError(
            f"每个用户最多创建 {settings.max_knowledge_bases_per_user} 个知识库",
            400,
        )

    kb = KnowledgeBase(id=new_uuid(), user_id=user_id, name=name)
    session.add(kb)
    await session.commit()
    await session.refresh(kb)
    return kb


async def delete_knowledge_base(session: AsyncSession, user_id: str, kb_id: str) -> None:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise KnowledgeBaseError("知识库不存在", 404)
    await session.delete(kb)
    await session.commit()
