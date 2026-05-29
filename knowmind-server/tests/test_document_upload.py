from unittest.mock import patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.base import Base
from app.db.session import get_db
from app.main import app
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


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


MINIMAL_PDF = b"%PDF-1.4\n1 0 obj<<>>endobj\ntrailer<<>>\n%%EOF"
SAMPLE_MD = b"# Test\n\nHello markdown."


@pytest.mark.asyncio
async def test_upload_pdf_creates_preview(async_client: AsyncClient) -> None:
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "doc@example.com", "password": "password123"},
    )
    assert reg.status_code == 200
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    kb = await async_client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "测试库"},
    )
    assert kb.status_code == 201
    kb_id = kb.json()["id"]

    with (
        patch("app.workers.document_tasks.process_document_task.delay", lambda *_a, **_k: None),
        patch("app.workers.document_tasks.run_document_ingest", lambda *_a, **_k: None),
    ):
        up = await async_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents",
            headers=headers,
            files=[("files", ("hello.pdf", MINIMAL_PDF, "application/pdf"))],
        )
    assert up.status_code == 200, up.text
    body = up.json()
    assert len(body["documents"]) == 1
    assert body["documents"][0]["status"] == "preview"
    assert body["documents"][0]["file_type"] == "pdf"
    assert body["documents"][0]["id"] in body["needs_preview"]

    listed = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
    )
    assert listed.status_code == 200
    assert len(listed.json()) == 1


@pytest.mark.asyncio
async def test_upload_markdown_creates_preview(async_client: AsyncClient) -> None:
    reg = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "md@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    kb = await async_client.post(
        "/api/v1/knowledge-bases",
        headers=headers,
        json={"name": "MD库"},
    )
    kb_id = kb.json()["id"]

    up = await async_client.post(
        f"/api/v1/knowledge-bases/{kb_id}/documents",
        headers=headers,
        files=[("files", ("note.md", SAMPLE_MD, "text/markdown"))],
    )
    assert up.status_code == 200, up.text
    body = up.json()
    doc = body["documents"][0]
    assert doc["status"] == "preview"
    assert doc["file_type"] == "markdown"
    assert doc["id"] in body["needs_preview"]

    preview = await async_client.get(
        f"/api/v1/knowledge-bases/{kb_id}/documents/{doc['id']}/parsed-content",
        headers=headers,
    )
    assert preview.status_code == 200
    assert "Hello markdown" in preview.json()["content"]

    with (
        patch("app.workers.document_tasks.process_document_task.delay", lambda *_a, **_k: None),
        patch("app.workers.document_tasks.run_document_ingest", lambda *_a, **_k: None),
    ):
        confirm = await async_client.post(
            f"/api/v1/knowledge-bases/{kb_id}/documents/{doc['id']}/confirm-import",
            headers=headers,
        )
    assert confirm.status_code == 200
    assert confirm.json()["document"]["status"] == "pending"
