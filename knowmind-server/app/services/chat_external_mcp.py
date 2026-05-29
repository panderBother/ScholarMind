"""对话中调用用户已启用的远程 URL 型 MCP 工具。"""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.config import settings
from app.core.logging_setup import log_info
from app.services.edgefn_client import ChatTurnResult, complete_chat_turn, turn_visible_text
from app.services.mcp_url_client import (
    McpToolBinding,
    binding_by_id,
    bindings_to_openai_tools,
    call_tool,
    discover_all_tools,
    parse_qualified_tool_name,
)

log = logging.getLogger(__name__)


@dataclass
class McpToolTraceEntry:
    qualified_name: str
    server_name: str
    tool_name: str
    arguments: str
    result: dict[str, Any]
    ok: bool


@dataclass
class ChatWithExternalMcpResult:
    reasoning: str = ""
    content: str = ""
    tool_traces: list[McpToolTraceEntry] = field(default_factory=list)
    discovery_errors: list[str] = field(default_factory=list)
    tools: list[McpToolBinding] = field(default_factory=list)


async def discover_external_mcp_tools(user_id: str) -> ChatWithExternalMcpResult:
    tools, errors = await discover_all_tools(user_id)
    return ChatWithExternalMcpResult(tools=tools, discovery_errors=errors)


async def complete_chat_with_external_mcp(
    messages: list[dict[str, Any]],
    *,
    user_id: str,
    tool_bindings: list[McpToolBinding],
    on_tool: Callable[[McpToolTraceEntry], Awaitable[None]] | None = None,
) -> ChatWithExternalMcpResult:
    if not tool_bindings:
        turn = await complete_chat_turn(messages)
        return ChatWithExternalMcpResult(
            reasoning=turn.reasoning,
            content=turn_visible_text(turn) or turn.content,
        )

    openai_tools = bindings_to_openai_tools(tool_bindings)
    by_qualified = {b.openai_name: b for b in tool_bindings}
    servers = binding_by_id(user_id)
    working = list(messages)
    traces: list[McpToolTraceEntry] = []
    last_reasoning = ""
    last_content = ""
    max_rounds = max(1, settings.external_mcp_max_rounds)

    for _ in range(max_rounds):
        turn = await complete_chat_turn(working, tools=openai_tools)
        last_reasoning = turn.reasoning or last_reasoning
        last_content = turn.content or last_content

        if not turn.tool_calls:
            return ChatWithExternalMcpResult(
                reasoning=last_reasoning,
                content=turn_visible_text(turn) or last_content,
                tool_traces=traces,
                tools=tool_bindings,
            )

        working.append(
            {
                "role": "assistant",
                "content": turn.content or None,
                "tool_calls": turn.tool_calls,
            },
        )

        for tc in turn.tool_calls:
            fn = tc.get("function") or {}
            qualified = str(fn.get("name") or "")
            args_raw = str(fn.get("arguments") or "{}")
            try:
                args_obj = json.loads(args_raw) if args_raw.strip() else {}
            except json.JSONDecodeError:
                args_obj = {}
            if not isinstance(args_obj, dict):
                args_obj = {}

            parsed = parse_qualified_tool_name(qualified)
            binding_meta = by_qualified.get(qualified)
            if parsed is None or binding_meta is None:
                result = {"error": f"未知 MCP 工具: {qualified}"}
                ok = False
                server_name = "?"
                tool_name = qualified
            else:
                custom_id, tool_name = parsed
                server = servers.get(custom_id)
                if server is None:
                    result = {"error": f"MCP 服务未启用或不存在: {custom_id}"}
                    ok = False
                    server_name = binding_meta.server_name
                else:
                    try:
                        result = await call_tool(server, tool_name, args_obj)
                        ok = not bool(result.get("isError")) and "error" not in result
                        server_name = server.display_name
                        log_info("[external_mcp] 调用 %s/%s ok=%s", server_name, tool_name, ok)
                    except Exception as e:
                        result = {"error": str(e)}
                        ok = False
                        server_name = server.display_name
                        tool_name = tool_name
                        log.warning("external_mcp call failed: %s", e)

            entry = McpToolTraceEntry(
                qualified_name=qualified,
                server_name=server_name,
                tool_name=tool_name if parsed else qualified,
                arguments=args_raw,
                result=result,
                ok=ok,
            )
            traces.append(entry)
            if on_tool is not None:
                await on_tool(entry)

            working.append(
                {
                    "role": "tool",
                    "tool_call_id": tc.get("id"),
                    "content": json.dumps(result, ensure_ascii=False),
                },
            )

    return ChatWithExternalMcpResult(
        reasoning=last_reasoning,
        content=last_content or "（已达外部 MCP 调用轮次上限，请重试或简化请求）",
        tool_traces=traces,
        tools=tool_bindings,
    )


