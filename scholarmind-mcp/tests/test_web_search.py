import pytest

from web_search.operations import build_search_queries, extract_urls, format_results_markdown, web_search


def test_extract_urls() -> None:
    urls = extract_urls("请看 https://example.com/foo 和 http://test.org")
    assert "https://example.com/foo" in urls
    assert "http://test.org" in urls


def test_build_search_queries_includes_url() -> None:
    qs = build_search_queries("https://codingmind.com/cn/projects 干啥的")
    assert any("codingmind" in q for q in qs)


@pytest.mark.asyncio
async def test_web_search_duckduckgo_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BRAVE_SEARCH_API_KEY", raising=False)
    payload = await web_search("Python programming language", max_results=3)
    assert payload["status"] in ("ok", "no_results")
    md = format_results_markdown(payload)
    assert "联网搜索" in md or "失败" in md or "未返回" in md
