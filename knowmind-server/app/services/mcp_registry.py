"""用户 MCP 工具注册表：内置开关 + 外部导入配置（JSON 文件持久化）。"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.config import _SERVER_ROOT
from app.models.mcp_schemas import (
    BuiltinMcpToolDto,
    CustomMcpToolDto,
    ImportMcpResponse,
    McpServerConfig,
    McpToolsResponse,
)

_REGISTRY_DIR = _SERVER_ROOT / "data" / "mcp" / "users"

_BUILTIN_AVAILABLE = frozenset({"file_writer", "web_search"})

_BUILTIN_CATALOG: list[dict[str, str]] = [
    {
        "id": "arxiv",
        "name": "arXiv",
        "description": "按关键词或 ID 检索 arXiv 论文元数据",
    },
    {
        "id": "semantic_scholar",
        "name": "Semantic Scholar",
        "description": "论文引用图与 TL;DR 摘要",
    },
    {
        "id": "web_search",
        "name": "Web Search",
        "description": "对话前联网检索（可选 Brave API；无 Key 时用 DuckDuckGo）",
    },
    {
        "id": "file_writer",
        "name": "File Writer",
        "description": "Web 对话中读写本地文本文件（受控路径）",
    },
]

_DEFAULT_BUILTIN_ENABLED = {
    "arxiv": False,
    "semantic_scholar": False,
    "web_search": False,
    "file_writer": False,
}


def _path_for_user(user_id: str) -> Path:
    _REGISTRY_DIR.mkdir(parents=True, exist_ok=True)
    safe = "".join(c if c.isalnum() or c in "-_" else "_" for c in user_id)
    return _REGISTRY_DIR / f"{safe}.json"


def _default_registry() -> dict[str, Any]:
    return {
        "builtin": {k: {"enabled": v} for k, v in _DEFAULT_BUILTIN_ENABLED.items()},
        "custom": [],
    }


def load_registry(user_id: str) -> dict[str, Any]:
    path = _path_for_user(user_id)
    if not path.is_file():
        return _default_registry()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return _default_registry()
    if not isinstance(data, dict):
        return _default_registry()
    reg = _default_registry()
    if isinstance(data.get("builtin"), dict):
        for k, v in data["builtin"].items():
            if isinstance(v, dict) and "enabled" in v:
                reg["builtin"][k] = {"enabled": bool(v["enabled"])}
    if isinstance(data.get("custom"), list):
        reg["custom"] = [c for c in data["custom"] if isinstance(c, dict)]
    return reg


def save_registry(user_id: str, data: dict[str, Any]) -> None:
    path = _path_for_user(user_id)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def is_builtin_enabled(user_id: str, tool_id: str) -> bool:
    reg = load_registry(user_id)
    entry = reg.get("builtin", {}).get(tool_id)
    if isinstance(entry, dict):
        return bool(entry.get("enabled"))
    return bool(_DEFAULT_BUILTIN_ENABLED.get(tool_id, False))


def list_tools(user_id: str) -> McpToolsResponse:
    reg = load_registry(user_id)
    builtin_out: list[BuiltinMcpToolDto] = []
    for item in _BUILTIN_CATALOG:
        tid = item["id"]
        enabled = bool(reg.get("builtin", {}).get(tid, {}).get("enabled", False))
        available = tid in _BUILTIN_AVAILABLE
        builtin_out.append(
            BuiltinMcpToolDto(
                id=tid,
                name=item["name"],
                description=item["description"],
                enabled=enabled,
                available=available,
            ),
        )
    custom_out: list[CustomMcpToolDto] = []
    for raw in reg.get("custom", []):
        try:
            custom_out.append(_custom_from_dict(raw))
        except (TypeError, ValueError):
            continue
    return McpToolsResponse(builtin=builtin_out, custom=custom_out)


def update_builtin(user_id: str, tool_id: str, enabled: bool) -> McpToolsResponse:
    if tool_id not in _DEFAULT_BUILTIN_ENABLED:
        raise ValueError(f"未知内置工具: {tool_id}")
    reg = load_registry(user_id)
    reg.setdefault("builtin", {})[tool_id] = {"enabled": enabled}
    save_registry(user_id, reg)
    return list_tools(user_id)


def _custom_from_dict(raw: dict[str, Any]) -> CustomMcpToolDto:
    cfg = raw.get("config") or {}
    return CustomMcpToolDto(
        id=str(raw.get("id") or uuid.uuid4()),
        name=str(raw.get("name") or "custom"),
        description=str(raw.get("description") or "外部导入的 MCP Server"),
        enabled=bool(raw.get("enabled", True)),
        source=str(raw.get("source") or "import"),
        config=McpServerConfig(
            command=cfg.get("command"),
            args=list(cfg.get("args") or []),
            env=dict(cfg.get("env") or {}),
            url=cfg.get("url"),
        ),
        imported_at=str(raw.get("imported_at") or ""),
    )


def _parse_import_payload(raw_json: str) -> dict[str, dict[str, Any]]:
    data = json.loads(raw_json)
    if isinstance(data, dict) and "mcpServers" in data:
        servers = data["mcpServers"]
    elif isinstance(data, dict):
        servers = data
    else:
        raise ValueError("JSON 须为对象，且包含 mcpServers 或为 mcpServers 本身")
    if not isinstance(servers, dict):
        raise ValueError("mcpServers 须为对象")
    out: dict[str, dict[str, Any]] = {}
    for name, cfg in servers.items():
        if isinstance(cfg, dict):
            out[str(name)] = cfg
    return out


def import_mcp_json(user_id: str, raw_json: str) -> ImportMcpResponse:
    servers = _parse_import_payload(raw_json)
    reg = load_registry(user_id)
    custom: list[dict[str, Any]] = list(reg.get("custom") or [])
    existing_names = {c.get("name") for c in custom}
    imported = 0
    skipped = 0
    now = datetime.now(timezone.utc).isoformat()

    for name, cfg in servers.items():
        if name in existing_names:
            skipped += 1
            continue
        entry = {
            "id": str(uuid.uuid4()),
            "name": name,
            "description": "从外部 mcp.json 导入",
            "enabled": True,
            "source": "import",
            "config": {
                "command": cfg.get("command"),
                "args": cfg.get("args") or [],
                "env": cfg.get("env") or {},
                "url": cfg.get("url"),
            },
            "imported_at": now,
        }
        custom.append(entry)
        existing_names.add(name)
        imported += 1

    reg["custom"] = custom
    save_registry(user_id, reg)
    dto = list_tools(user_id)
    return ImportMcpResponse(imported=imported, skipped=skipped, custom=dto.custom)


def update_custom_enabled(user_id: str, custom_id: str, enabled: bool) -> McpToolsResponse:
    reg = load_registry(user_id)
    found = False
    for c in reg.get("custom", []):
        if c.get("id") == custom_id:
            c["enabled"] = enabled
            found = True
            break
    if not found:
        raise ValueError("未找到该 MCP 配置")
    save_registry(user_id, reg)
    return list_tools(user_id)


def delete_custom(user_id: str, custom_id: str) -> McpToolsResponse:
    reg = load_registry(user_id)
    before = len(reg.get("custom", []))
    reg["custom"] = [c for c in reg.get("custom", []) if c.get("id") != custom_id]
    if len(reg["custom"]) == before:
        raise ValueError("未找到该 MCP 配置")
    save_registry(user_id, reg)
    return list_tools(user_id)
