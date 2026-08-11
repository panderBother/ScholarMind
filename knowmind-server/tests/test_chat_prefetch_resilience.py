import asyncio

import pytest

from app.models.schemas import ChatRequest
from app.services.chat_prefetch import PrefetchResult
from app.services.chat_service import _run_prefetch_with_retry, _stream_prefetch_bundle


@pytest.mark.asyncio
async def test_prefetch_retries_once_before_success(monkeypatch) -> None:
    attempts = 0

    async def flaky() -> str:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise RuntimeError("temporary")
        return "ok"

    async def no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("app.services.chat_service.asyncio.sleep", no_sleep)
    assert await _run_prefetch_with_retry("web_search", flaky) == "ok"
    assert attempts == 2


@pytest.mark.asyncio
async def test_prefetch_source_failure_does_not_cancel_other_sources() -> None:
    async def ok(value: str) -> str:
        await asyncio.sleep(0)
        return value

    async def fail() -> str:
        await asyncio.sleep(0)
        raise RuntimeError("arxiv unavailable")

    req = ChatRequest(message="test", web_search=True, arxiv=True)
    web_task = asyncio.create_task(ok("## web result"))
    arxiv_task = asyncio.create_task(fail())
    final: PrefetchResult | None = None
    events: list[str] = []

    async for item in _stream_prefetch_bundle(
        req=req,
        user_id=None,
        kb_context="",
        rag_task=None,
        web_task=web_task,
        arxiv_task=arxiv_task,
        s2_task=None,
        attachment_task=None,
        rag_hits=[],
        rag_diag={},
    ):
        if isinstance(item, PrefetchResult):
            final = item
        else:
            events.append(item)

    assert final is not None
    assert final.web_injected is True
    assert "## web result" in final.merged_context
    assert final.errors == {"arxiv_search": "arxiv unavailable"}
    assert any(
        '"step": "arxiv_search"' in event and '"status": "error"' in event for event in events
    )
