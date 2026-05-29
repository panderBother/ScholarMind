"""远程 URL 型 MCP 客户端：连接、列举工具、调用工具。"""

from __future__ import annotations

import json
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings
from app.services import mcp_registry

log = logging.getLogger(__name__)

SEP = "::"


@dataclass
class McpUrlBinding:
    custom_id: str
    display_name: str
    url: str
    headers: dict[str, str]


@dataclass
class McpToolBinding:
    custom_id: str
    server_name: str
    tool_name: str
    openai_name: str
    description: str
    parameters: dict[str, Any]


def list_enabled_url_bindings(user_id: str) -> list[McpUrlBinding]:
    """已启用且配置了 url 的外部 MCP。"""
    out: list[McpUrlBinding] = []
    for c in mcp_registry.list_tools(user_id).custom:
        if not c.enabled:
            continue
        url = (c.config.url or "").strip()
        if not url:
            continue
        hdrs = {str(k): str(v) for k, v in (c.config.env or {}).items() if str(k).startswith("HEADER_")}
        out.append(
            McpUrlBinding(
                custom_id=c.id,
                display_name=c.name,
                url=url,
                headers=hdrs,
            ),
        )
    return out


def qualified_tool_name(custom_id: str, tool_name: str) -> str:
    return f"{custom_id}{SEP}{tool_name}"


def parse_qualified_tool_name(qualified: str) -> tuple[str, str] | None:
    if SEP not in qualified:
        return None
    cid, _, tname = qualified.partition(SEP)
    if not cid or not tname:
        return None
    return cid, tname


@asynccontextmanager
async def _open_session(url: str, headers: dict[str, str]) -> AsyncIterator[ClientSession]:
    timeout = float(settings.external_mcp_connect_timeout)
    read_timeout = float(settings.external_mcp_read_timeout)
    last_err: Exception | None = None

    try:
        async with streamablehttp_client(
            url,
            headers=headers or None,
            timeout=timeout,
            sse_read_timeout=read_timeout,
        ) as streams:
            read_stream, write_stream, _ = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
                return
    except Exception as e:
        last_err = e
        log.warning("MCP streamable_http connect failed url=%s: %s", url, e)

    try:
        async with sse_client(
            url,
            headers=headers or None,
            timeout=timeout,
            sse_read_timeout=read_timeout,
        ) as streams:
            read_stream, write_stream = streams
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                yield session
                return
    except Exception as e:
        last_err = e
        log.warning("MCP sse connect failed url=%s: %s", url, e)

    raise RuntimeError(f"无法连接 MCP 服务 {url}: {last_err}")


async def discover_tools(binding: McpUrlBinding) -> list[McpToolBinding]:
    async with _open_session(binding.url, binding.headers) as session:
        listed = await session.list_tools()
    tools = listed.tools if listed else []
    out: list[McpToolBinding] = []
    for t in tools:
        name = str(getattr(t, "name", "") or "")
        if not name:
            continue
        schema = getattr(t, "inputSchema", None) or {"type": "object", "properties": {}}
        if hasattr(schema, "model_dump"):
            schema = schema.model_dump()
        elif not isinstance(schema, dict):
            schema = {"type": "object", "properties": {}}
        out.append(
            McpToolBinding(
                custom_id=binding.custom_id,
                server_name=binding.display_name,
                tool_name=name,
                openai_name=qualified_tool_name(binding.custom_id, name),
                description=(getattr(t, "description", None) or f"{binding.display_name} / {name}")[:2000],
                parameters=schema,
            ),
        )
    return out


async def discover_all_tools(user_id: str) -> tuple[list[McpToolBinding], list[str]]:
    """返回 (工具列表, 各 server 发现失败信息)。"""
    bindings = list_enabled_url_bindings(user_id)
    all_tools: list[McpToolBinding] = []
    errors: list[str] = []
    for b in bindings:
        try:
            found = await discover_tools(b)
            all_tools.extend(found)
            log.info("mcp url discover ok server=%s tools=%s", b.display_name, len(found))
        except Exception as e:
            msg = f"{b.display_name}: {e!s}"
            errors.append(msg)
            log.warning("mcp url discover failed %s", msg)
    return all_tools, errors


def bindings_to_openai_tools(bindings: list[McpToolBinding]) -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "function": {
                "name": b.openai_name,
                "description": b.description,
                "parameters": b.parameters,
            },
        }
        for b in bindings
    ]


async def call_tool(binding: McpUrlBinding, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    async with _open_session(binding.url, binding.headers) as session:
        result = await session.call_tool(tool_name, arguments=arguments)
    content_parts: list[str] = []
    if result.content:
        for block in result.content:
            text = getattr(block, "text", None)
            if text:
                content_parts.append(str(text))
            else:
                content_parts.append(str(block))
    text = "\n".join(content_parts).strip()
    structured = getattr(result, "structuredContent", None)
    if structured is not None:
        return {"text": text, "structured": structured, "isError": bool(getattr(result, "isError", False))}
    if text:
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return {"text": text, "isError": bool(getattr(result, "isError", False))}
    return {"isError": bool(getattr(result, "isError", False))}


def binding_by_id(user_id: str) -> dict[str, McpUrlBinding]:
    return {b.custom_id: b for b in list_enabled_url_bindings(user_id)}
