import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.base import Base
from app.db.session import get_db
from app.main import app


@pytest.fixture
async def async_client():
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


@pytest.mark.asyncio
async def test_register_login_me_kb_flow(async_client: AsyncClient) -> None:
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    body = reg.json()
    token = body["access_token"]
    assert body["user"]["email"] == "flow@example.com"

    dup = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "flow@example.com", "password": "password123"},
    )
    assert dup.status_code == 409

    me = await async_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    assert me.json()["email"] == "flow@example.com"

    kbs = await async_client.get(
        "/api/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert kbs.status_code == 200
    assert kbs.json() == []

    create = await async_client.post(
        "/api/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
        json={"name": "我的知识库"},
    )
    assert create.status_code == 201, create.text
    kb_id = create.json()["id"]

    listed = await async_client.get(
        "/api/v1/knowledge-bases",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert len(listed.json()) == 1

    deleted = await async_client.delete(
        f"/api/v1/knowledge-bases/{kb_id}",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert deleted.status_code == 204
