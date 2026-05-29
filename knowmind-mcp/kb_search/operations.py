"""调用 KnowMind REST API 检索知识库。"""

from __future__ import annotations

import os

import httpx


def _require_env(name: str) -> str:
    val = (os.environ.get(name) or "").strip()
    if not val:
        raise RuntimeError(f"缺少环境变量 {name}")
    return val


async def search_kb(query: str, *, limit: int = 20) -> dict:
    base = _require_env("KNOWMIND_API_BASE").rstrip("/")
    kb_id = _require_env("KNOWMIND_KB_ID")
    token = (os.environ.get("KNOWMIND_ACCESS_TOKEN") or "").strip()
    q = (query or "").strip()
    if not q:
        raise ValueError("query 不能为空")

    cap = max(1, min(int(limit), 50))
    url = f"{base}/knowledge-bases/{kb_id}/search"
    headers: dict[str, str] = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.get(url, params={"q": q, "limit": cap}, headers=headers)
        resp.raise_for_status()
        data = resp.json()

    items = data.get("items") or []
    lines: list[str] = []
    for i, row in enumerate(items, 1):
        title = row.get("title") or "未命名"
        snippet = (row.get("snippet") or "").strip()
        score = row.get("score")
        lines.append(f"### {i}. {title} (score={score})\n{snippet}")
    markdown = "\n\n".join(lines) if lines else "（未命中已发布条目）"
    return {
        "query": data.get("query") or q,
        "total": data.get("total", len(items)),
        "items": items,
        "markdown": markdown,
    }
