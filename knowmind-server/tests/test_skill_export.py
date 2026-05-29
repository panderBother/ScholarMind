"""Skill / MCP 导出 API 测试。"""

from __future__ import annotations

import json

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


async def _auth_and_kb(client: AsyncClient) -> tuple[dict[str, str], str]:
    reg = await client.post(
        "/api/v1/auth/register",
        json={"email": "export@example.com", "password": "password123"},
    )
    assert reg.status_code == 200, reg.text
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    kb = await client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "导出测试库"},
    )
    assert kb.status_code == 201
    return headers, kb.json()["id"]


@pytest.mark.asyncio
async def test_export_skill_markdown(async_client: AsyncClient) -> None:
    headers, kb_id = await _auth_and_kb(async_client)
    res = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/export/skill",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    assert "text/markdown" in res.headers.get("content-type", "")
    body = res.text
    assert kb_id in body
    assert "search_kb" in body
    assert "export/skill" not in body or "工具与集成" in body


@pytest.mark.asyncio
async def test_export_skill_json(async_client: AsyncClient) -> None:
    headers, kb_id = await _auth_and_kb(async_client)
    res = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/export/skill",
        headers=headers,
        params={"format": "json"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["name"] == "search_kb"
    assert data["kb_id"] == kb_id
    assert "parameters" in data
    assert kb_id in data["endpoint"]


@pytest.mark.asyncio
async def test_export_mcp_manifest(async_client: AsyncClient) -> None:
    headers, kb_id = await _auth_and_kb(async_client)
    res = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/export/mcp-manifest",
        headers=headers,
    )
    assert res.status_code == 200, res.text
    data = json.loads(res.text)
    assert "mcpServers" in data
    assert len(data["mcpServers"]) == 1
    srv = next(iter(data["mcpServers"].values()))
    assert srv["env"]["KNOWMIND_KB_ID"] == kb_id
    assert "kb_search.server" in " ".join(srv["args"])
