from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.orm import KnowledgeBase, KnowledgeItem, new_uuid
from app.services.knowledge_category_service import ensure_default_category


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


async def count_items_by_kb_ids(session: AsyncSession, kb_ids: list[str]) -> dict[str, int]:
    if not kb_ids:
        return {}
    q = (
        select(KnowledgeItem.kb_id, func.count())
        .where(KnowledgeItem.kb_id.in_(kb_ids), KnowledgeItem.lifecycle_status != "archived")
        .group_by(KnowledgeItem.kb_id)
    )
    r = await session.execute(q)
    return {str(kb_id): int(n) for kb_id, n in r.all()}


async def count_items_for_kb(session: AsyncSession, kb_id: str) -> int:
    counts = await count_items_by_kb_ids(session, [kb_id])
    return counts.get(kb_id, 0)


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
    await session.flush()
    await ensure_default_category(session, user_id, kb.id)
    await session.commit()
    await session.refresh(kb)
    return kb


async def get_knowledge_base(session: AsyncSession, user_id: str, kb_id: str) -> KnowledgeBase:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise KnowledgeBaseError("知识库不存在", 404)
    return kb


async def update_knowledge_base(
    session: AsyncSession, user_id: str, kb_id: str, name: str
) -> KnowledgeBase:
    kb = await get_knowledge_base(session, user_id, kb_id)
    name = name.strip()
    if not name:
        raise KnowledgeBaseError("知识库名称不能为空", 400)
    kb.name = name
    await session.commit()
    await session.refresh(kb)
    return kb


async def delete_knowledge_base(session: AsyncSession, user_id: str, kb_id: str) -> None:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise KnowledgeBaseError("知识库不存在", 404)
    await session.delete(kb)
    await session.commit()
