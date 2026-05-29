import json

from app.services import mcp_registry
from app.services.mcp_url_client import (
    list_enabled_url_bindings,
    parse_qualified_tool_name,
    qualified_tool_name,
)


def test_import_skips_command_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mcp_registry, "_REGISTRY_DIR", tmp_path)
    uid = "user-url-1"
    raw = json.dumps(
        {
            "mcpServers": {
                "local-only": {"command": "node", "args": ["server.js"]},
                "remote": {"url": "https://mcp.example.com/sse"},
            },
        },
    )
    out = mcp_registry.import_mcp_json(uid, raw)
    assert out.imported == 1
    assert out.skipped == 1
    tools = mcp_registry.list_tools(uid)
    assert len(tools.custom) == 1
    assert tools.custom[0].name == "remote"
    assert tools.custom[0].config.url == "https://mcp.example.com/sse"


def test_list_enabled_url_bindings_respects_toggle(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mcp_registry, "_REGISTRY_DIR", tmp_path)
    uid = "user-url-2"
    raw = json.dumps(
        {
            "mcpServers": {
                "svc-a": {"url": "https://a.example/mcp"},
                "svc-b": {"url": "https://b.example/mcp"},
            },
        },
    )
    mcp_registry.import_mcp_json(uid, raw)
    dto = mcp_registry.list_tools(uid)
    assert len(dto.custom) == 2
    cid = dto.custom[0].id
    mcp_registry.update_custom_enabled(uid, cid, False)

    bindings = list_enabled_url_bindings(uid)
    assert len(bindings) == 1
    assert bindings[0].url.startswith("https://")


def test_qualified_tool_name_roundtrip() -> None:
    q = qualified_tool_name("abc-123", "search")
    assert q == "abc-123::search"
    parsed = parse_qualified_tool_name(q)
    assert parsed == ("abc-123", "search")
    assert parse_qualified_tool_name("no-sep") is None
