from app.services.mcp_url_client import enrich_mcp_tool_result, mcp_tool_result_ok


def test_mcp_tool_result_ok_with_null_error_key():
    assert mcp_tool_result_ok({"error": None, "url": "https://example.com/a.png"}) is True


def test_mcp_tool_result_ok_with_error_message():
    assert mcp_tool_result_ok({"error": "timeout"}) is False


def test_enrich_adds_media_urls():
    raw = {"error": None, "text": "ok https://storage.bizyair.cn/outputs/x.png"}
    out = enrich_mcp_tool_result(raw)
    assert out["media_urls"] == ["https://storage.bizyair.cn/outputs/x.png"]
