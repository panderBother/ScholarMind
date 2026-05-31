"""arXiv API 检索（Atom feed）。"""

from __future__ import annotations

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any
from urllib.parse import quote

import httpx

log = logging.getLogger("arxiv")

ATOM_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}
_ARXIV_ID_RE = re.compile(
    r"(?:arxiv\.org/(?:abs|pdf)/)?(\d{4}\.\d{4,5}(?:v\d+)?|[a-z\-]+(?:\.[A-Z]{2})?/\d{7}(?:v\d+)?)",
    re.IGNORECASE,
)


def extract_arxiv_ids(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _ARXIV_ID_RE.finditer(text or ""):
        aid = m.group(1)
        if aid not in seen:
            seen.add(aid)
            out.append(aid)
    return out


async def search_arxiv(query: str, *, max_results: int = 5) -> dict[str, Any]:
    q = (query or "").strip()
    if not q:
        return {"query": q, "max_results": max_results, "items": []}

    ids = extract_arxiv_ids(q)
    if ids:
        id_query = " OR ".join(f"id:{i}" for i in ids[:5])
        search_q = id_query
    else:
        search_q = f"all:{q}"

    url = (
        "https://export.arxiv.org/api/query?"
        f"search_query={quote(search_q)}&start=0&max_results={min(max_results, 20)}&sortBy=relevance"
    )
    items: list[dict[str, Any]] = []
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
            r = await client.get(url, headers={"User-Agent": "KnowMind/1.0"})
            r.raise_for_status()
            root = ET.fromstring(r.text)
        for entry in root.findall("atom:entry", ATOM_NS):
            title = (entry.findtext("atom:title", default="", namespaces=ATOM_NS) or "").strip()
            summary = (entry.findtext("atom:summary", default="", namespaces=ATOM_NS) or "").strip()
            published = entry.findtext("atom:published", default="", namespaces=ATOM_NS) or ""
            authors = [
                (a.findtext("atom:name", default="", namespaces=ATOM_NS) or "").strip()
                for a in entry.findall("atom:author", ATOM_NS)
            ]
            authors = [a for a in authors if a]
            link = ""
            for link_el in entry.findall("atom:link", ATOM_NS):
                if link_el.get("rel") == "alternate":
                    link = link_el.get("href") or ""
                    break
            arxiv_id = ""
            raw_id = entry.findtext("atom:id", default="", namespaces=ATOM_NS) or ""
            if "/abs/" in raw_id:
                arxiv_id = raw_id.rsplit("/abs/", 1)[-1]
            items.append(
                {
                    "arxiv_id": arxiv_id,
                    "title": title.replace("\n", " "),
                    "authors": authors,
                    "published": published[:10],
                    "summary": summary[:1200],
                    "url": link or (f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else ""),
                },
            )
    except Exception as e:
        log.warning("arxiv search failed: %s", e)
        return {"query": q, "max_results": max_results, "items": [], "error": str(e)}

    return {"query": q, "max_results": max_results, "items": items}


def format_arxiv_markdown(payload: dict[str, Any]) -> str:
    items = payload.get("items") or []
    if not items:
        err = payload.get("error")
        if err:
            return f"## arXiv 检索\n\n（检索失败：{err}）"
        return "## arXiv 检索\n\n（未找到相关信息。）"
    lines = ["## arXiv 检索摘录", ""]
    for i, it in enumerate(items, 1):
        title = it.get("title") or "无标题"
        authors = ", ".join(it.get("authors") or []) or "未知作者"
        pub = it.get("published") or ""
        aid = it.get("arxiv_id") or ""
        url = it.get("url") or ""
        summary = (it.get("summary") or "").strip()
        if len(summary) > 500:
            summary = summary[:500] + "…"
        lines.append(f"### [{i}] {title}")
        lines.append(f"- **arXiv ID**：{aid or '—'} · **日期**：{pub or '—'}")
        lines.append(f"- **作者**：{authors}")
        if url:
            lines.append(f"- **链接**：{url}")
        if summary:
            lines.append(f"\n{summary}\n")
    return "\n".join(lines)
