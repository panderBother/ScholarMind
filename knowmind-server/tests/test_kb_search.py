import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import app


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
        yield client
    app.dependency_overrides.clear()
    await engine.dispose()
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_kb_hybrid_search_published_item(async_client: AsyncClient) -> None:
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "search@example.com", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    create_kb = await async_client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "检索测试库"},
    )
    assert create_kb.status_code == 201
    kb_id = create_kb.json()["id"]

    created_cat = await async_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/categories",
        headers=headers,
        json={"name": "测试分类", "parent_id": None, "sort_order": 0},
    )
    assert created_cat.status_code == 201, created_cat.text
    category_id = created_cat.json()["id"]

    unique = "HybridSearchUniqueToken42"
    create_item = await async_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/items",
        headers=headers,
        json={
            "title": "测试条目",
            "content": f"本文讨论 {unique} 与深度学习基础概念。",
            "category_id": category_id,
            "publish": True,
        },
    )
    assert create_item.status_code == 201, create_item.text
    item_id = create_item.json()["id"]

    search = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/search",
        headers=headers,
        params={"q": unique},
    )
    assert search.status_code == 200, search.text
    body = search.json()
    assert body["total"] >= 1
    assert any(h["item_id"] == item_id for h in body["items"])

    draft_only = "ZetaDraftOnlyKeyword99"
    draft = await async_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/items",
        headers=headers,
        json={
            "title": "草稿",
            "content": f"草稿独有 {draft_only}",
            "category_id": category_id,
            "publish": False,
        },
    )
    assert draft.status_code == 201

    draft_search = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/search",
        headers=headers,
        params={"q": draft_only},
    )
    assert draft_search.status_code == 200
    assert draft_search.json()["total"] == 0

    unauth = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/search",
        params={"q": unique},
    )
    assert unauth.status_code == 401


@pytest.mark.asyncio
async def test_archived_item_excluded_from_hybrid_search(async_client: AsyncClient) -> None:
    """AC-M-05：归档（下架）后混合检索不再命中；仅 published 参与检索。"""
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "archive@example.com", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    headers = {"Authorization": f"Bearer {reg.json()['access_token']}"}

    kb_id = (
        await async_client.post(
            "/api/v1/knowledge-bases",
            headers=headers,
            json={"name": "归档测试库"},
        )
    ).json()["id"]

    category_id = (
        await async_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/categories",
            headers=headers,
            json={"name": "分类", "parent_id": None, "sort_order": 0},
        )
    ).json()["id"]

    unique = "ArchiveExcludeToken77"
    item_id = (
        await async_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/items",
            headers=headers,
            json={
                "title": "将归档条目",
                "content": f"独有词 {unique} 用于验证归档后不可检索。",
                "category_id": category_id,
                "publish": True,
            },
        )
    ).json()["id"]

    before = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/search",
        headers=headers,
        params={"q": unique},
    )
    assert before.status_code == 200, before.text
    assert before.json()["total"] >= 1
    assert any(h["item_id"] == item_id for h in before.json()["items"])

    archived = await async_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/items/{item_id}/archive",
        headers=headers,
    )
    assert archived.status_code == 200, archived.text
    assert archived.json()["lifecycle_status"] == "archived"

    after = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/search",
        headers=headers,
        params={"q": unique},
    )
    assert after.status_code == 200, after.text
    assert after.json()["total"] == 0


@pytest.mark.asyncio
async def test_kb_search_empty_query_rejected(async_client: AsyncClient) -> None:
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "search2@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    kb = await async_client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "库"},
    )
    kb_id = kb.json()["id"]
    bad = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/search",
        headers=headers,
        params={"q": ""},
    )
    assert bad.status_code == 422
