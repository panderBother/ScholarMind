import httpx

from app.services.mcp_url_client import _format_connect_error


def test_format_connect_error_401() -> None:
    req = httpx.Request("POST", "https://api.bizyair.cn/w/v1/mcp/527")
    resp = httpx.Response(401, request=req)
    err = httpx.HTTPStatusError("Unauthorized", request=req, response=resp)
    msg = _format_connect_error(err)
    assert "401" in msg
    assert "Authorization" in msg
