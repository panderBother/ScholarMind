"""联网搜索核心逻辑（Brave API + DuckDuckGo 即时答案回退 + URL 页面抓取）。"""

from __future__ import annotations

import logging
import os
import re
from typing import Any
from urllib.parse import urlparse

import httpx

log = logging.getLogger("web_search")

DEFAULT_MAX_RESULTS = 5
_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)


def extract_urls(text: str) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for m in _URL_RE.finditer(text or ""):
        u = m.group(0).rstrip(".,;:)」】）")
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out


def build_search_queries(user_message: str) -> list[str]:
    """从用户消息生成 1～3 条检索词（含 URL 站点名）。"""
    msg = (user_message or "").strip()
    if not msg:
        return []
    urls = extract_urls(msg)
    queries: list[str] = []
    seen_q: set[str] = set()

    def add(q: str) -> None:
        q = q.strip()
        if q and q not in seen_q:
            seen_q.add(q)
            queries.append(q)

    for url in urls[:2]:
        add(url)
        try:
            host = urlparse(url).netloc or ""
        except Exception:  # noqa: BLE001
            host = ""
        if host:
            add(f"{host} 网站介绍")
            add(f"site:{host}")

    add(msg[:200])
    return queries[:3]


def _brave_key() -> str | None:
    return (os.environ.get("BRAVE_SEARCH_API_KEY") or "").strip() or None


async def _search_brave(query: str, *, max_results: int) -> list[dict[str, str]]:
    key = _brave_key()
    if not key:
        return []
    url = "https://api.search.brave.com/res/v1/web/search"
    headers = {"X-Subscription-Token": key, "Accept": "application/json"}
    params = {"q": query, "count": min(max_results, 20)}
    async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
        r = await client.get(url, headers=headers, params=params)
        r.raise_for_status()
        data = r.json()
    web = data.get("web") if isinstance(data, dict) else None
    results = web.get("results") if isinstance(web, dict) else None
    if not isinstance(results, list):
        return []
    out: list[dict[str, str]] = []
    for item in results[:max_results]:
        if not isinstance(item, dict):
            continue
        out.append(
            {
                "title": str(item.get("title") or ""),
                "url": str(item.get("url") or ""),
                "snippet": str(item.get("description") or ""),
            },
        )
    return out


async def _search_duckduckgo_instant(query: str, *, max_results: int) -> list[dict[str, str]]:
    """无需 API Key 的轻量回退（摘要 + 相关主题）。"""
    params = {"q": query, "format": "json", "no_html": 1, "skip_disambig": 1}
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0)) as client:
        r = await client.get("https://api.duckduckgo.com/", params=params)
        r.raise_for_status()
        data = r.json()
    if not isinstance(data, dict):
        return []
    out: list[dict[str, str]] = []
    abstract = data.get("AbstractText")
    if isinstance(abstract, str) and abstract.strip():
        out.append(
            {
                "title": str(data.get("Heading") or query),
                "url": str(data.get("AbstractURL") or ""),
                "snippet": abstract.strip(),
            },
        )

    def walk(topics: Any) -> None:
        if len(out) >= max_results or not isinstance(topics, list):
            return
        for t in topics:
            if len(out) >= max_results:
                break
            if isinstance(t, dict) and "Topics" in t:
                walk(t.get("Topics"))
            elif isinstance(t, dict) and t.get("Text"):
                out.append(
                    {
                        "title": str(t.get("Text", ""))[:120],
                        "url": str(t.get("FirstURL") or ""),
                        "snippet": str(t.get("Text") or ""),
                    },
                )

    walk(data.get("RelatedTopics"))
    return out[:max_results]


async def fetch_url_page_text(url: str, *, max_chars: int = 6000) -> dict[str, str] | None:
    """通过 Jina Reader 抓取网页正文（无需 API Key）。"""
    u = (url or "").strip()
    if not u.lower().startswith(("http://", "https://")):
        return None
    reader_url = f"https://r.jina.ai/{u}"
    headers = {"Accept": "text/plain", "User-Agent": "ScholarMind/1.0"}
    try:
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(25.0),
            follow_redirects=True,
        ) as client:
            r = await client.get(reader_url, headers=headers)
            r.raise_for_status()
            body = (r.text or "").strip()
    except Exception as e:  # noqa: BLE001
        log.warning("url fetch failed url=%r err=%s", u[:80], e)
        return None
    if not body:
        return None
    if len(body) > max_chars:
        body = body[:max_chars] + "\n…（正文已截断）"
    return {"title": u, "url": u, "snippet": body}


async def web_search(query: str, *, max_results: int = DEFAULT_MAX_RESULTS) -> dict[str, Any]:
    """
    执行联网搜索。返回 { query, results: [{title, url, snippet}], provider, status }。
    """
    q = (query or "").strip()
    if not q:
        return {"query": "", "results": [], "provider": "none", "status": "empty"}

    results: list[dict[str, str]] = []
    provider = "duckduckgo"
    try:
        results = await _search_brave(q, max_results=max_results)
        if results:
            provider = "brave"
    except Exception as e:  # noqa: BLE001
        log.warning("brave search failed: %s", e)

    if not results:
        try:
            results = await _search_duckduckgo_instant(q, max_results=max_results)
            provider = "duckduckgo"
        except Exception as e:  # noqa: BLE001
            log.warning("duckduckgo search failed: %s", e)
            return {
                "query": q,
                "results": [],
                "provider": provider,
                "status": "error",
                "error": str(e),
            }

    log.info("web_search ok provider=%s query=%r hits=%s", provider, q[:80], len(results))
    return {
        "query": q,
        "results": results,
        "provider": provider,
        "status": "ok" if results else "no_results",
    }


async def web_search_for_message(
    user_message: str,
    *,
    max_results: int = DEFAULT_MAX_RESULTS,
) -> dict[str, Any]:
    """合并多查询 + URL 页面抓取，供对话注入。"""
    msg = (user_message or "").strip()
    urls = extract_urls(msg)
    merged: list[dict[str, str]] = []
    seen_url: set[str] = set()
    providers: list[str] = []

    for url in urls[:2]:
        page = await fetch_url_page_text(url)
        if page and page.get("snippet"):
            merged.append({**page, "title": f"网页正文：{page.get('title', url)}"})
            providers.append("url_fetch")

    for q in build_search_queries(msg):
        if len(merged) >= max_results:
            break
        payload = await web_search(q, max_results=max_results)
        prov = str(payload.get("provider") or "")
        if prov:
            providers.append(prov)
        for hit in payload.get("results") or []:
            if not isinstance(hit, dict):
                continue
            u = str(hit.get("url") or "")
            if u and u in seen_url:
                continue
            if u:
                seen_url.add(u)
            merged.append(
                {
                    "title": str(hit.get("title") or ""),
                    "url": u,
                    "snippet": str(hit.get("snippet") or ""),
                },
            )
            if len(merged) >= max_results:
                break

    provider = "+".join(dict.fromkeys(providers)) or "none"
    return {
        "query": msg,
        "results": merged[:max_results],
        "provider": provider,
        "status": "ok" if merged else "no_results",
    }


def format_results_markdown(payload: dict[str, Any]) -> str:
    """格式化为可注入 RAG/对话 system 的 Markdown。"""
    if payload.get("status") == "error":
        return f"（联网搜索失败：{payload.get('error', '未知错误')}）"
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        return (
            "（联网搜索未返回有效结果。请根据用户问题尽力回答；"
            "若涉及具体网址，可说明未能抓取到该页内容，勿假装已浏览该站。）"
        )
    lines = [
        "## 联网搜索结果（请优先依据下列摘录作答）",
        f"用户问题：{payload.get('query', '')}",
        f"来源：{payload.get('provider', '')}",
        "",
    ]
    for i, hit in enumerate(results, 1):
        if not isinstance(hit, dict):
            continue
        title = hit.get("title") or f"结果 {i}"
        url = hit.get("url") or ""
        snippet = hit.get("snippet") or ""
        lines.append(f"### [{i}] {title}")
        if url:
            lines.append(f"- 链接：{url}")
        if snippet:
            lines.append(f"- 摘要：{snippet}")
        lines.append("")
    return "\n".join(lines).strip()
