"""一键专家 Agent：基于知识库已发布条目生成 system_prompt 并独立对话。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.orm import ExpertAgent, KnowledgeBase, new_uuid
from app.services.knowledge_item_service import list_items


class ExpertError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def _ensure_kb(session: AsyncSession, user_id: str, kb_id: str) -> KnowledgeBase:
    kb = await session.get(KnowledgeBase, kb_id)
    if kb is None or kb.user_id != user_id:
        raise ExpertError("知识库不存在", 404)
    return kb


def build_system_prompt_from_items(kb_name: str, items: list) -> str:
    lines = [
        f"你是「{kb_name}」领域的专家助手。",
        "请用专业、清晰的中文回答；优先依据下列知识库已发布条目与对话中检索到的摘录作答。",
        "若资料不足以回答，请明确说明，不要编造事实。",
        "回答可使用 Markdown（标题、列表、代码块）。",
    ]
    if not items:
        lines.append("\n（当前知识库尚无已发布条目，请提示用户先发布知识后再深度问答。）")
        return "\n\n".join(lines)

    lines.append("\n## 知识库已发布条目摘要\n")
    for i, item in enumerate(items[:30], 1):
        snippet = (item.summary or item.content or "").strip().replace("\n", " ")
        if len(snippet) > 280:
            snippet = snippet[:280] + "…"
        tags = item.tags if isinstance(item.tags, list) and item.tags else []
        tag_hint = f"（标签：{', '.join(str(t) for t in tags[:5])}）" if tags else ""
        lines.append(f"{i}. **{item.title}**{tag_hint}\n   {snippet or '（无正文摘要）'}")
    return "\n\n".join(lines)


async def generate_system_prompt(session: AsyncSession, user_id: str, kb_id: str) -> str:
    kb = await _ensure_kb(session, user_id, kb_id)
    items = await list_items(session, user_id, kb_id, lifecycle_status="published")
    return build_system_prompt_from_items(kb.name, items)


async def create_expert(
    session: AsyncSession,
    user_id: str,
    *,
    kb_id: str,
    name: str | None = None,
    description: str | None = None,
) -> ExpertAgent:
    kb = await _ensure_kb(session, user_id, kb_id)
    prompt = await generate_system_prompt(session, user_id, kb_id)
    display_name = (name or "").strip() or f"{kb.name} 专家"
    row = ExpertAgent(
        id=new_uuid(),
        user_id=user_id,
        kb_id=kb.id,
        name=display_name[:100],
        description=(description or f"基于「{kb.name}」已发布条目自动生成").strip()[:500] or None,
        system_prompt=prompt,
    )
    session.add(row)
    await session.flush()
    return row


async def list_experts(
    session: AsyncSession,
    user_id: str,
    *,
    kb_id: str | None = None,
    limit: int = 50,
) -> list[ExpertAgent]:
    stmt = select(ExpertAgent).where(ExpertAgent.user_id == user_id).order_by(ExpertAgent.updated_at.desc())
    if kb_id:
        stmt = stmt.where(ExpertAgent.kb_id == kb_id)
    stmt = stmt.limit(max(1, min(limit, 100)))
    q = await session.execute(stmt)
    return list(q.scalars().all())


async def get_expert(session: AsyncSession, user_id: str, expert_id: str) -> ExpertAgent:
    row = await session.get(ExpertAgent, expert_id)
    if row is None or row.user_id != user_id:
        raise ExpertError("专家不存在", 404)
    return row


async def delete_expert(session: AsyncSession, user_id: str, expert_id: str) -> None:
    row = await get_expert(session, user_id, expert_id)
    await session.delete(row)


async def refresh_expert_prompt(session: AsyncSession, user_id: str, expert_id: str) -> ExpertAgent:
    row = await get_expert(session, user_id, expert_id)
    row.system_prompt = await generate_system_prompt(session, user_id, row.kb_id)
    await session.flush()
    return row


def expert_to_schema(row: ExpertAgent) -> dict:
    return {
        "id": row.id,
        "kb_id": row.kb_id,
        "name": row.name,
        "description": row.description,
        "system_prompt": row.system_prompt,
        "created_at": row.created_at,
        "updated_at": row.updated_at,
    }
