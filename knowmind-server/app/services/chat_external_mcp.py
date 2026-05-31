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
from app.services.chat_external_mcp_parse import (
    parse_text_tool_calls,
    strip_text_tool_calls,
    synthetic_tool_call,
)
from app.services.mcp_tool_args import coerce_arguments_for_schema, schema_enum_summary
from app.services.mcp_url_client import (
    McpToolBinding,
    binding_by_id,
    bindings_to_openai_tools,
    call_tool,
    discover_all_tools,
    parse_qualified_tool_name,
)

log = logging.getLogger(__name__)


def _use_native_external_mcp_tools() -> bool:
    return settings.external_mcp_tool_mode.strip().lower() == "native"


def _is_edgefn_tool_choice_error(exc: BaseException) -> bool:
    msg = str(exc).lower()
    return "tool" in msg and (
        "choice" in msg
        or "tool-call-parser" in msg
        or "enable-auto-tool-choice" in msg
        or ("invalidrequestbody" in msg and "tool" in msg)
    )


def _combined_model_text(reasoning: str, content: str) -> str:
    parts = [p.strip() for p in (reasoning, content) if p and p.strip()]
    return "\n\n".join(parts)


def _resolve_tool_calls(
    turn: ChatTurnResult,
    *,
    known_names: set[str],
    allow_text_parse: bool = True,
) -> list[dict[str, Any]]:
    if turn.tool_calls:
        return turn.tool_calls
    if not allow_text_parse:
        return []
    parsed = parse_text_tool_calls(_combined_model_text(turn.reasoning, turn.content), known_names=known_names)
    if not parsed:
        return []
    log_info("[external_mcp] 从模型正文解析到 %s 个工具调用（prompt 模式）", len(parsed))
    return [synthetic_tool_call(name, args) for name, args in parsed]


def _tool_catalog_lines(bindings: list[McpToolBinding]) -> str:
    lines: list[str] = []
    for b in bindings:
        lines.append(f"- `{b.openai_name}`（{b.server_name} / {b.tool_name}）: {b.description[:400]}")
        enum_lines = schema_enum_summary(b.parameters)
        if enum_lines:
            lines.append("  参数约束（违反会导致 BizyAir 校验失败）:")
            lines.extend(enum_lines)
        else:
            schema = json.dumps(b.parameters, ensure_ascii=False)
            if len(schema) > 600:
                schema = schema[:600] + "…"
            lines.append(f"  参数 JSON schema: {schema}")
    return "\n".join(lines)


def _prompt_mcp_block(bindings: list[McpToolBinding]) -> str:
    catalog = _tool_catalog_lines(bindings)
    return f"""
## 外部 MCP 工具（prompt 模式，必须遵守）

需要调用远程工具时，在回复中使用下列格式（`function` 后的工具名必须与列表中的 **完整名称** 一致）：

<|tool_calls_begin|> <|tool_call_begin|> function <|tool_sep|> 完整工具名
```json
{{"参数名": "参数值"}}
```
<|tool_call_end|> <|tool_calls_end|>

可用工具：
{catalog}

写出工具块后停止，等待系统执行；勿编造图片链接或工具结果。
**比例/尺寸参数禁止使用 16:9、9:16 等未在「参数约束」中列出的值。**
若无需调用工具，正常回答且不要输出上述块。
""".strip()


def inject_external_mcp_tool_instructions(
    messages: list[dict[str, Any]],
    bindings: list[McpToolBinding],
) -> list[dict[str, Any]]:
    block = _prompt_mcp_block(bindings)
    out: list[dict[str, Any]] = [dict(m) for m in messages]
    if not out:
        return [{"role": "system", "content": block}]
    if out[0].get("role") != "system":
        out.insert(0, {"role": "system", "content": block})
        return out
    content = str(out[0].get("content") or "")
    if block[:40] not in content:
        out[0] = {**out[0], "content": f"{content}\n\n{block}".strip()}
    return out


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


async def _execute_mcp_tool_calls(
    tool_calls: list[dict[str, Any]],
    *,
    by_qualified: dict[str, McpToolBinding],
    servers: dict[str, Any],
    traces: list[McpToolTraceEntry],
    on_tool: Callable[[McpToolTraceEntry], Awaitable[None]] | None,
) -> list[str]:
    result_lines: list[str] = []
    for tc in tool_calls:
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
                    schema = binding_meta.parameters if binding_meta else {}
                    args_obj, coerce_notes = coerce_arguments_for_schema(args_obj, schema)
                    if coerce_notes:
                        log_info("[external_mcp] 参数已修正: %s", "; ".join(coerce_notes))
                    result = await call_tool(server, tool_name, args_obj)
                    ok = not bool(result.get("isError")) and "error" not in result
                    server_name = server.display_name
                    log_info("[external_mcp] 调用 %s/%s ok=%s", server_name, tool_name, ok)
                except Exception as e:
                    result = {"error": str(e)}
                    ok = False
                    server_name = server.display_name
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
        result_lines.append(f"- {qualified}: {json.dumps(result, ensure_ascii=False)}")
    return result_lines


async def _complete_prompt(
    messages: list[dict[str, Any]],
    *,
    user_id: str,
    tool_bindings: list[McpToolBinding],
    on_tool: Callable[[McpToolTraceEntry], Awaitable[None]] | None,
) -> ChatWithExternalMcpResult:
    by_qualified = {b.openai_name: b for b in tool_bindings}
    servers = binding_by_id(user_id)
    working = inject_external_mcp_tool_instructions(messages, tool_bindings)
    traces: list[McpToolTraceEntry] = []
    last_reasoning = ""
    last_content = ""
    max_rounds = max(1, settings.external_mcp_max_rounds)

    for round_idx in range(max_rounds):
        turn = await complete_chat_turn(working)
        last_reasoning = turn.reasoning or last_reasoning
        last_content = turn.content or last_content
        combined = _combined_model_text(turn.reasoning, turn.content)
        tool_calls = _resolve_tool_calls(turn, known_names=set(by_qualified.keys()))
        log_info("[external_mcp] prompt round=%s parsed=%s", round_idx, len(tool_calls))

        if not tool_calls:
            visible = strip_text_tool_calls(turn_visible_text(turn) or last_content)
            return ChatWithExternalMcpResult(
                reasoning=strip_text_tool_calls(last_reasoning),
                content=visible,
                tool_traces=traces,
                tools=tool_bindings,
            )

        result_lines = await _execute_mcp_tool_calls(
            tool_calls,
            by_qualified=by_qualified,
            servers=servers,
            traces=traces,
            on_tool=on_tool,
        )
        working.append({"role": "assistant", "content": combined})
        working.append(
            {
                "role": "user",
                "content": "【系统】外部 MCP 工具已执行，结果如下。请用自然语言整理回复用户（含图片链接等），"
                "勿再输出 tool_calls 标记除非仍需继续调用：\n" + "\n".join(result_lines),
            },
        )

    return ChatWithExternalMcpResult(
        reasoning=strip_text_tool_calls(last_reasoning),
        content=strip_text_tool_calls(last_content) or "（已达外部 MCP 调用轮次上限，请重试或简化请求）",
        tool_traces=traces,
        tools=tool_bindings,
    )


async def _complete_native(
    messages: list[dict[str, Any]],
    *,
    user_id: str,
    tool_bindings: list[McpToolBinding],
    on_tool: Callable[[McpToolTraceEntry], Awaitable[None]] | None,
) -> ChatWithExternalMcpResult:
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
        tool_calls = _resolve_tool_calls(turn, known_names=set(by_qualified.keys()), allow_text_parse=False)

        if not tool_calls:
            visible = turn_visible_text(turn) or last_content
            visible = strip_text_tool_calls(visible)
            return ChatWithExternalMcpResult(
                reasoning=strip_text_tool_calls(last_reasoning),
                content=visible,
                tool_traces=traces,
                tools=tool_bindings,
            )

        working.append(
            {
                "role": "assistant",
                "content": turn.content or None,
                "tool_calls": tool_calls,
            },
        )

        for tc in tool_calls:
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
                        schema = binding_meta.parameters if binding_meta else {}
                        args_obj, coerce_notes = coerce_arguments_for_schema(args_obj, schema)
                        if coerce_notes:
                            log_info("[external_mcp] 参数已修正: %s", "; ".join(coerce_notes))
                        result = await call_tool(server, tool_name, args_obj)
                        ok = not bool(result.get("isError")) and "error" not in result
                        server_name = server.display_name
                        log_info("[external_mcp] 调用 %s/%s ok=%s", server_name, tool_name, ok)
                    except Exception as e:
                        result = {"error": str(e)}
                        ok = False
                        server_name = server.display_name
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
        reasoning=strip_text_tool_calls(last_reasoning),
        content=strip_text_tool_calls(last_content) or "（已达外部 MCP 调用轮次上限，请重试或简化请求）",
        tool_traces=traces,
        tools=tool_bindings,
    )


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

    log_info("[external_mcp] tool_mode=%s", settings.external_mcp_tool_mode)
    if _use_native_external_mcp_tools():
        try:
            return await _complete_native(messages, user_id=user_id, tool_bindings=tool_bindings, on_tool=on_tool)
        except RuntimeError as e:
            if _is_edgefn_tool_choice_error(e):
                log.warning("external_mcp native failed, fallback to prompt: %s", e)
                return await _complete_prompt(messages, user_id=user_id, tool_bindings=tool_bindings, on_tool=on_tool)
            raise
    return await _complete_prompt(messages, user_id=user_id, tool_bindings=tool_bindings, on_tool=on_tool)
