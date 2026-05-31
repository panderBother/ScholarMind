"""外部 MCP 工具参数：按 schema enum 校验与常见比例修正。"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

# 常见非法比例 → BizyAir 等 T2I 工作流允许的取值
_ASPECT_ALIASES: dict[str, str] = {
    "16:9": "3:2",
    "9:16": "2:3",
    "4:3": "3:2",
    "3:4": "2:3",
    "16/9": "3:2",
    "9/16": "2:3",
}


def _prop_for_arg_key(key: str, properties: dict[str, Any]) -> dict[str, Any] | None:
    if key in properties and isinstance(properties[key], dict):
        return properties[key]
    suffix = key.split(".")[-1] if "." in key else key
    for pname, pdef in properties.items():
        if not isinstance(pdef, dict):
            continue
        if pname == key or pname.endswith(suffix) or suffix in pname:
            return pdef
    return None


def _pick_enum_value(raw: str, enum: list[Any]) -> str:
    sval = str(raw).strip()
    allowed = [str(v) for v in enum]
    if sval in allowed:
        return sval
    mapped = _ASPECT_ALIASES.get(sval.replace(" ", ""))
    if mapped and mapped in allowed:
        return mapped
    lower_map = {a.lower(): a for a in allowed}
    if sval.lower() in lower_map:
        return lower_map[sval.lower()]
    return allowed[0]


def coerce_arguments_for_schema(
    arguments: dict[str, Any],
    schema: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """
    将参数中不符合 enum 的取值修正为 schema 允许值。
    返回 (新参数, 修正说明列表)。
    """
    if not arguments or not isinstance(schema, dict):
        return arguments, []
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return arguments, []
    out = dict(arguments)
    notes: list[str] = []
    for key, val in list(out.items()):
        pdef = _prop_for_arg_key(str(key), props)
        if not pdef:
            continue
        enum = pdef.get("enum")
        if not isinstance(enum, list) or not enum:
            continue
        sval = str(val).strip()
        picked = _pick_enum_value(sval, enum)
        if picked != sval:
            out[key] = picked
            notes.append(f"{key}: {sval!r} → {picked!r}（允许 {enum}）")
            log.info("mcp args coerce %s: %s -> %s", key, sval, picked)
    return out, notes


def schema_enum_summary(schema: dict[str, Any]) -> list[str]:
    """生成供 prompt 展示的 enum 约束摘要。"""
    lines: list[str] = []
    props = schema.get("properties") or {}
    if not isinstance(props, dict):
        return lines
    for pname, pdef in props.items():
        if not isinstance(pdef, dict):
            continue
        enum = pdef.get("enum")
        if isinstance(enum, list) and enum:
            lines.append(f"    - `{pname}` **必须**是以下之一: {', '.join(str(v) for v in enum)}")
    return lines
