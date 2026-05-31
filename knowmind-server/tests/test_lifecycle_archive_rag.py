"""AC-M-05：归档后不参与混合检索 / RAG（service 层直测，绕开 API 序列化问题）。"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.models.orm import User
from app.services import knowledge_category_service as cat_svc
from app.services import knowledge_item_service as item_svc
from app.services import knowledge_base_service as kb_svc
from app.services.rag_context import search_kb
from app.services.search_service import hybrid_search


@pytest.fixture
async def session(tmp_path, monkeypatch):
    whoosh_dir = tmp_path / "whoosh"
    chroma_dir = tmp_path / "chroma"
    monkeypatch.setenv("WHOOSH_INDEX_ROOT", str(whoosh_dir))
    monkeypatch.setenv("CHROMA_DATA_PATH", str(chroma_dir))
    monkeypatch.setenv("EMBEDDING_MODE", "hash")
    get_settings.cache_clear()

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    @event.listens_for(engine.sync_engine, "connect")
    def _sqlite_enable_fk(dbapi_connection, connection_record) -> None:  # noqa: ARG001
        cur = dbapi_connection.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        sess.add(
            User(
                id="user-lifecycle-1",
                email="lifecycle1@test.local",
                password_hash="x",
            ),
        )
        sess.add(
            User(
                id="user-lifecycle-2",
                email="lifecycle2@test.local",
                password_hash="x",
            ),
        )
        await sess.commit()
        yield sess
    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_archive_excludes_from_hybrid_search_and_rag(session: AsyncSession) -> None:
    user_id = "user-lifecycle-1"
    kb = await kb_svc.create_knowledge_base(session, user_id, "生命周期库")
    cat = await cat_svc.ensure_default_category(session, user_id, kb.id)

    unique = "LifecycleArchiveToken55"
    item = await item_svc.create_item(
        session,
        user_id,
        kb.id,
        title="测试",
        content=f"内容含 {unique} 关键词。",
        category_id=cat.id,
        publish=True,
    )
    assert item.lifecycle_status == "published"

    hits_before = await hybrid_search(session, user_id, kb.id, unique, limit=10)
    assert any(h.item_id == item.id for h in hits_before)

    rag_before = await search_kb(session, user_id, kb.id, unique)
    assert any(h.item_id == item.id for h in rag_before.hits)

    archived = await item_svc.archive_item(session, user_id, kb.id, item.id)
    assert archived.lifecycle_status == "archived"

    hits_after = await hybrid_search(session, user_id, kb.id, unique, limit=10)
    assert not any(h.item_id == item.id for h in hits_after)

    rag_after = await search_kb(session, user_id, kb.id, unique)
    assert not any(h.item_id == item.id for h in rag_after.hits)
    assert item.id not in rag_after.top_item_ids


@pytest.mark.asyncio
async def test_draft_excluded_from_hybrid_search(session: AsyncSession) -> None:
    user_id = "user-lifecycle-2"
    kb = await kb_svc.create_knowledge_base(session, user_id, "草稿库")
    cat = await cat_svc.ensure_default_category(session, user_id, kb.id)

    draft_only = "DraftOnlyKeyword66"
    await item_svc.create_item(
        session,
        user_id,
        kb.id,
        title="草稿",
        content=f"仅草稿 {draft_only}",
        category_id=cat.id,
        publish=False,
    )

    hits = await hybrid_search(session, user_id, kb.id, draft_only, limit=10)
    assert hits == []


@pytest.mark.asyncio
async def test_orphan_index_excluded_after_item_deleted(session: AsyncSession) -> None:
    """DB 条目已删但向量未清时，检索不应再返回幽灵引用。"""
    user_id = "user-lifecycle-1"
    kb = await kb_svc.create_knowledge_base(session, user_id, "孤儿索引库")
    cat = await cat_svc.ensure_default_category(session, user_id, kb.id)

    unique = "OrphanGhostToken77"
    item = await item_svc.create_item(
        session,
        user_id,
        kb.id,
        title="将被删除",
        content=f"幽灵内容 {unique} 测试。",
        category_id=cat.id,
        publish=True,
    )

    hits_before = await hybrid_search(session, user_id, kb.id, unique, limit=10)
    assert any(h.item_id == item.id for h in hits_before)

    await session.delete(item)
    await session.commit()

    hits_after = await hybrid_search(session, user_id, kb.id, unique, limit=10)
    assert not any(h.item_id == item.id for h in hits_after)

    rag_after = await search_kb(session, user_id, kb.id, unique)
    assert rag_after.hits == []
