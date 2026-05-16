import json

from app.services import mcp_registry


def test_import_and_toggle_builtin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mcp_registry, "_REGISTRY_DIR", tmp_path)
    uid = "user-test-1"
    raw = json.dumps(
        {
            "mcpServers": {
                "my-external": {"command": "node", "args": ["server.js"]},
            },
        },
    )
    out = mcp_registry.import_mcp_json(uid, raw)
    assert out.imported == 1
    tools = mcp_registry.list_tools(uid)
    assert len(tools.custom) == 1
    assert tools.custom[0].name == "my-external"

    mcp_registry.update_builtin(uid, "file_writer", False)
    assert not mcp_registry.is_builtin_enabled(uid, "file_writer")
