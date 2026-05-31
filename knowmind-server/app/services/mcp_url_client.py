"""外部 MCP 客户端：远程 URL（SSE / Streamable HTTP）与本地 stdio（command）。"""

from __future__ import annotations

import json
import logging
import os
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, AsyncIterator

from mcp import ClientSession
from mcp.client.sse import sse_client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamablehttp_client

from app.core.config import settings
from app.services import mcp_registry

log = logging.getLogger(__name__)

SEP = "::"


def _format_connect_error(err: Exception) -> str:
    """把 TaskGroup / HTTPStatusError 等包装异常转成可读信息。"""
    seen: set[int] = set()

    def walk(e: BaseException) -> str | None:
        oid = id(e)
        if oid in seen:
            return None
        seen.add(oid)
        import httpx

        if isinstance(e, httpx.HTTPStatusError):
            status = e.response.status_code
            if status == 401:
                return "401 Unauthorized（请在 MCP 配置的 HTTP 请求头中填写 Authorization: Bearer 你的BizyAir_API_Key）"
            if status == 403:
                return "403 Forbidden（API Key 无效或无权访问该 MCP）"
            return f"HTTP {status} {e.response.reason_phrase}"
        msg = str(e).strip()
        if isinstance(e, BaseExceptionGroup):
            for sub in e.exceptions:
                detail = walk(sub)
                if detail:
                    return detail
        cause = e.__cause__
        if isinstance(cause, BaseException):
            detail = walk(cause)
            if detail:
                return detail
        return msg or type(e).__name__

    return walk(err) or type(err).__name__


@dataclass
class McpUrlBinding:
    custom_id: str
    display_name: str
    url: str | None = None
    command: str | None = None
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    headers: dict[str, str] = field(default_factory=dict)


@dataclass
class McpToolBinding:
    custom_id: str
    server_name: str
    tool_name: str
    openai_name: str
    description: str
    parameters: dict[str, Any]


def list_enabled_url_bindings(user_id: str) -> list[McpUrlBinding]:
    """已启用且配置了 url 或 command 的外部 MCP。"""
    out: list[McpUrlBinding] = []
    for c in mcp_registry.list_tools(user_id).custom:
        if not c.enabled:
            continue
        url = (c.config.url or "").strip()
        command = (c.config.command or "").strip()
        if not url and not command:
            continue
        if url:
            hdrs = dict(c.config.headers or {})
            for k, v in (c.config.env or {}).items():
                if str(k).startswith("HEADER_"):
                    hdrs[str(k)[len("HEADER_") :]] = str(v)
            out.append(
                McpUrlBinding(
                    custom_id=c.id,
                    display_name=c.name,
                    url=url,
                    headers=hdrs,
                ),
            )
        else:
            env = {str(k): str(v) for k, v in (c.config.env or {}).items() if not str(k).startswith("HEADER_")}
            cwd = (c.config.cwd or "").strip() or None
            out.append(
                McpUrlBinding(
                    custom_id=c.id,
                    display_name=c.name,
                    command=command,
                    args=[str(a) for a in (c.config.args or [])],
                    env=env,
                    cwd=cwd,
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
async def _stdio_session(binding: McpUrlBinding) -> AsyncIterator[ClientSession]:
    merged_env = {**os.environ, **binding.env} if binding.env else None
    params = StdioServerParameters(
        command=str(binding.command),
        args=list(binding.args or []),
        env=merged_env,
        cwd=binding.cwd,
    )
    async with stdio_client(params) as streams:
        read_stream, write_stream = streams
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            yield session


@asynccontextmanager
async def _url_session(binding: McpUrlBinding) -> AsyncIterator[ClientSession]:
    url = (binding.url or "").strip()
    if not url:
        raise RuntimeError("MCP 配置缺少 url")
    timeout = float(settings.external_mcp_connect_timeout)
    read_timeout = float(settings.external_mcp_read_timeout)
    headers = binding.headers or None
    last_err: Exception | None = None

    try:
        async with streamablehttp_client(
            url,
            headers=headers,
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
        log.warning(
            "MCP streamable_http connect failed url=%s: %s",
            url,
            _format_connect_error(e),
        )

    try:
        async with sse_client(
            url,
            headers=headers,
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
        log.warning(
            "MCP sse connect failed url=%s: %s",
            url,
            _format_connect_error(e),
        )

    raise RuntimeError(f"无法连接 MCP 服务 {url}: {_format_connect_error(last_err) if last_err else 'unknown'}")


@asynccontextmanager
async def _open_session(binding: McpUrlBinding) -> AsyncIterator[ClientSession]:
    if binding.command:
        async with _stdio_session(binding) as session:
            yield session
        return
    async with _url_session(binding) as session:
        yield session


async def discover_tools(binding: McpUrlBinding) -> list[McpToolBinding]:
    async with _open_session(binding) as session:
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
            log.info("mcp discover ok server=%s tools=%s", b.display_name, len(found))
        except Exception as e:
            msg = f"{b.display_name}: {e!s}"
            errors.append(msg)
            log.warning("mcp discover failed %s", msg)
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
    async with _open_session(binding) as session:
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
