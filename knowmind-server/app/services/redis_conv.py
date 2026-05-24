from __future__ import annotations

import json
import logging
from typing import Any

from app.core.config import get_settings
from app.core.memory_constants import MEMORY_REDIS_RECENT_CAP, MEMORY_REDIS_TTL_SECONDS

log = logging.getLogger(__name__)

_client: Any = None


def _redis_url() -> str:
    return get_settings().redis_url


def _get_client() -> Any:
    global _client
    if _client is None:
        import redis.asyncio as redis

        _client = redis.from_url(_redis_url(), decode_responses=True)
    return _client


def recent_key(conversation_id: str) -> str:
    return f"conv:{conversation_id}:recent"


async def get_recent_messages(conversation_id: str) -> list[dict[str, Any]] | None:
    try:
        r = _get_client()
        raw = await r.get(recent_key(conversation_id))
        if not raw:
            return None
        data = json.loads(raw)
        if isinstance(data, list):
            return data
    except Exception as e:
        log.warning("redis get recent failed: %s", e)
    return None


async def set_recent_messages(conversation_id: str, rows: list[dict[str, Any]]) -> None:
    cap = MEMORY_REDIS_RECENT_CAP
    trimmed = rows[-cap:] if len(rows) > cap else rows
    try:
        r = _get_client()
        await r.set(
            recent_key(conversation_id),
            json.dumps(trimmed, ensure_ascii=False),
            ex=MEMORY_REDIS_TTL_SECONDS,
        )
    except Exception as e:
        log.warning("redis set recent failed: %s", e)
