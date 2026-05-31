"""Semantic Scholar Graph API 检索。"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

log = logging.getLogger("semantic_scholar")

S2_BASE = "https://api.semanticscholar.org/graph/v1"


def _api_key() -> str | None:
    return (os.environ.get("SEMANTIC_SCHOLAR_API_KEY") or "").strip() or None


async def search_semantic_scholar(query: str, *, max_results: int = 5) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"query": q, "papers": []}

    fields = "title,authors,year,abstract,url,externalIds,citationCount,tldr"
    params = {"query": q, "limit": min(max_results, 20), "fields": fields}
    headers: dict[str, str] = {"User-Agent": "KnowMind/1.0"}
    key = _api_key()
    if key:
        headers["x-api-key"] = key

    papers: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            r = await client.get(f"{S2_BASE}/paper/search", params=params, headers=headers)
            r.raise_for_status()
            data = r.json()
        for raw in (data.get("data") or [])[:max_results]:
            if not isinstance(raw, dict):
                continue
            authors = [
                (a.get("name") or "").strip()
                for a in (raw.get("authors") or [])
                if isinstance(a, dict)
            ]
            authors = [a for a in authors if a]
            ext = raw.get("externalIds") if isinstance(raw.get("externalIds"), dict) else {}
            tldr_obj = raw.get("tldr") if isinstance(raw.get("tldr"), dict) else {}
            tldr = (tldr_obj.get("text") or "").strip()
            papers.append(
                {
                    "paper_id": raw.get("paperId") or "",
                    "title": (raw.get("title") or "").strip(),
                    "authors": authors,
                    "year": raw.get("year"),
                    "abstract": ((raw.get("abstract") or "")[:1200]).strip(),
                    "tldr": tldr,
                    "url": raw.get("url") or "",
                    "arxiv_id": ext.get("ArXiv") if ext else None,
                    "citation_count": raw.get("citationCount"),
                },
            )
    except Exception as e:
        log.warning("semantic scholar search failed: %s", e)
        return {"query": q, "papers": [], "error": str(e)}

    return {"query": q, "papers": papers}


def format_semantic_scholar_markdown(payload: dict[str, Any]) -> str:
    papers = payload.get("papers") or []
    if not papers:
        err = payload.get("error")
        if err:
            return f"## Semantic Scholar 检索\n\n（检索失败：{err}）"
        return "## Semantic Scholar 检索\n\n（未找到相关信息。）"
    lines = ["## Semantic Scholar 检索摘录", ""]
    for i, p in enumerate(papers, 1):
        title = p.get("title") or "无标题"
        authors = ", ".join(p.get("authors") or []) or "未知作者"
        year = p.get("year") or "—"
        cites = p.get("citation_count")
        cite_hint = f" · **引用**：{cites}" if cites is not None else ""
        url = p.get("url") or ""
        tldr = (p.get("tldr") or "").strip()
        abstract = (p.get("abstract") or "").strip()
        snippet = tldr or abstract
        if len(snippet) > 500:
            snippet = snippet[:500] + "…"
        lines.append(f"### [{i}] {title}")
        lines.append(f"- **年份**：{year}{cite_hint}")
        lines.append(f"- **作者**：{authors}")
        if p.get("arxiv_id"):
            lines.append(f"- **arXiv**：{p['arxiv_id']}")
        if url:
            lines.append(f"- **链接**：{url}")
        if snippet:
            lines.append(f"\n{snippet}\n")
    return "\n".join(lines)
