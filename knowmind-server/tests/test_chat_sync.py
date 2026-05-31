import json
from unittest.mock import AsyncMock, patch

import pytest

from app.models.schemas import ChatRequest, ChatResponse
from app.services.chat_sync import collect_chat_response


@pytest.mark.asyncio
async def test_collect_chat_response_merges_deltas() -> None:
    req = ChatRequest(message="hi", knowledge_base_id=None)

    async def fake_stream(*_args, **_kwargs):
        yield f"data: {json.dumps({'type': 'trace_id', 'trace_id': 't1'})}\n\n"
        yield f"data: {json.dumps({'type': 'delta', 'text': '你'})}\n\n"
        yield f"data: {json.dumps({'type': 'delta', 'text': '好'})}\n\n"

    with patch("app.services.chat_sync.iter_chat_stream", fake_stream):
        out = await collect_chat_response(req, session=AsyncMock(), user_id="u1")

    assert isinstance(out, ChatResponse)
    assert out.reply == "你好"
    assert out.trace_id == "t1"


@pytest.mark.asyncio
async def test_collect_chat_response_error_only() -> None:
    req = ChatRequest(message="x", knowledge_base_id=None)

    async def fake_stream(*_args, **_kwargs):
        yield f"data: {json.dumps({'type': 'error', 'message': 'boom'})}\n\n"

    with patch("app.services.chat_sync.iter_chat_stream", fake_stream):
        out = await collect_chat_response(req, session=AsyncMock(), user_id="u1")

    assert "boom" in out.reply
