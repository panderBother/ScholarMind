import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app
from app.models.orm import User
from app.services.rag_logging_service import RagHit
from app.services.search_service import HybridSearchHit
from app.services.usage_analytics_service import (
    record_chat_turn,
    record_rag_cites,
    record_search_hits,
)


@pytest.fixture
async def async_client(tmp_path, monkeypatch):
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

    async def override_db():
        async with factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client, factory
    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_analytics_overview_and_trend(async_client) -> None:
    client, factory = async_client

    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "analytics@example.com", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    create_kb = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "热度测试库"},
    )
    assert create_kb.status_code == 201
    kb_id = create_kb.json()["id"]

    create_cat = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/categories",
        headers=headers,
        json={"name": "默认分类", "parent_id": None, "sort_order": 0},
    )
    assert create_cat.status_code == 201, create_cat.text
    category_id = create_cat.json()["id"]

    create_item = await client.post(
        f"/api/v1/knowledge-bases/{kb_id}/items",
        headers=headers,
        json={
            "title": "条目A",
            "content": "测试内容",
            "category_id": category_id,
            "publish": False,
        },
    )
    assert create_item.status_code == 201, create_item.text
    item_id = create_item.json()["id"]

    async with factory() as session:
        user_id = (
            await session.execute(select(User.id).where(User.email == "analytics@example.com"))
        ).scalar_one()
        await record_search_hits(
            session,
            user_id=user_id,
            kb_id=kb_id,
            hits=[
                HybridSearchHit(
                    item_id=item_id,
                    chunk_id="c1",
                    doc_id="",
                    title="条目A",
                    text="t",
                    snippet="s",
                    score=0.8,
                    source_type="manual",
                    page=None,
                    tags=[],
                ),
            ],
        )
        await record_rag_cites(
            session,
            user_id=user_id,
            kb_id=kb_id,
            conversation_id=None,
            hits=[
                RagHit(
                    chunk_id="c1",
                    text="t",
                    doc_id="",
                    item_id=item_id,
                    page=0,
                    score=0.7,
                ),
            ],
        )
        await record_chat_turn(session, user_id=user_id, kb_id=kb_id, conversation_id=None)
        await session.commit()

    overview = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/analytics/overview?days=7",
        headers=headers,
    )
    assert overview.status_code == 200, overview.text
    body = overview.json()
    assert body["search_hits"] >= 1
    assert body["rag_cites"] >= 1
    assert body["chat_turns"] >= 1

    trend = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/analytics/trend?days=7",
        headers=headers,
    )
    assert trend.status_code == 200, trend.text
    assert len(trend.json()["points"]) == 7

    top = await client.get(
        f"/api/v1/knowledge-bases/{kb_id}/analytics/top-items?days=7",
        headers=headers,
    )
    assert top.status_code == 200, top.text
    assert top.json()["items"][0]["item_id"] == item_id
