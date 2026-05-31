import json

from app.services import mcp_registry


def test_import_and_toggle_builtin(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mcp_registry, "_REGISTRY_DIR", tmp_path)
    uid = "user-test-1"
    raw = json.dumps(
        {
            "mcpServers": {
                "my-external": {"url": "https://mcp.example.com/v1"},
            },
        },
    )
    out = mcp_registry.import_mcp_json(uid, raw)
    assert out.imported == 1
    tools = mcp_registry.list_tools(uid)
    assert len(tools.custom) == 1
    assert tools.custom[0].name == "my-external"
    assert tools.custom[0].config.url == "https://mcp.example.com/v1"

    mcp_registry.update_builtin(uid, "file_writer", False)
    assert not mcp_registry.is_builtin_enabled(uid, "file_writer")


def test_import_preserves_headers_and_update_custom(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(mcp_registry, "_REGISTRY_DIR", tmp_path)
    uid = "user-edit-1"
    raw = json.dumps(
        {
            "mcpServers": {
                "bizyair": {
                    "url": "https://api.bizyair.cn/w/v1/mcp/537",
                    "headers": {"Authorization": "Bearer test-key"},
                },
            },
        },
    )
    mcp_registry.import_mcp_json(uid, raw)
    tools = mcp_registry.list_tools(uid)
    assert tools.custom[0].config.headers == {"Authorization": "Bearer test-key"}

    cid = tools.custom[0].id
    from app.models.mcp_schemas import McpServerConfig, UpdateCustomMcpRequest

    updated = mcp_registry.update_custom(
        uid,
        cid,
        UpdateCustomMcpRequest(
            name="bizyair-edited",
            description="文生图",
            enabled=True,
            config=McpServerConfig(
                url="https://api.bizyair.cn/w/v1/mcp/999",
                headers={"Authorization": "Bearer new-key"},
            ),
        ),
    )
    row = updated.custom[0]
    assert row.name == "bizyair-edited"
    assert row.config.url == "https://api.bizyair.cn/w/v1/mcp/999"
    assert row.config.headers["Authorization"] == "Bearer new-key"
