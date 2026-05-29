"""Skill / MCP 配置导出：供 Cursor 等 Agent 平台调用知识库混合检索。"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from app.models.orm import KnowledgeBase

_SERVER_ROOT = Path(__file__).resolve().parents[2]
_DEFAULT_MCP_ROOT = _SERVER_ROOT.parent / "knowmind-mcp"


def _slugify(name: str, *, fallback: str = "kb") -> str:
    s = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", (name or "").strip(), flags=re.UNICODE)
    s = re.sub(r"-+", "-", s).strip("-").lower()
    return s[:48] or fallback


def _mcp_server_key(kb: KnowledgeBase) -> str:
    slug = _slugify(kb.name, fallback="kb")
    short = kb.id.replace("-", "")[:8]
    return f"knowmind-{slug}-{short}"


def build_skill_json(*, kb: KnowledgeBase, api_base: str) -> dict[str, Any]:
    base = api_base.rstrip("/")
    return {
        "name": "search_kb",
        "description": f"检索 KnowMind 知识库「{kb.name}」中已发布条目（语义 + 关键词混合检索）",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "检索关键词或自然语言问句",
                },
                "limit": {
                    "type": "integer",
                    "description": "返回条数上限，默认 20，最大 50",
                    "minimum": 1,
                    "maximum": 50,
                },
            },
            "required": ["query"],
        },
        "kb_id": kb.id,
        "kb_name": kb.name,
        "api_base": base,
        "endpoint": f"{base}/knowledge-bases/{kb.id}/search",
        "auth": "Authorization: Bearer <access_token>",
    }


def build_skill_markdown(*, kb: KnowledgeBase, api_base: str) -> str:
    base = api_base.rstrip("/")
    slug = _slugify(kb.name)
    search_url = f"{base}/knowledge-bases/{kb.id}/search"
    return f"""---
name: knowmind-search-{slug}
description: 检索 KnowMind 私有知识库「{kb.name}」中的已发布知识条目
---

# KnowMind 知识库检索 Skill

当用户的问题可能由知识库 **{kb.name}** 中的私有资料回答时，调用 `search_kb` 获取相关片段，再基于检索结果作答。

## 连接信息

| 项 | 值 |
|----|-----|
| API 基址 | `{base}` |
| 知识库 ID | `{kb.id}` |
| 知识库名称 | {kb.name} |
| 检索接口 | `GET {search_url}?q={{query}}&limit={{limit}}` |
| 鉴权 | `Authorization: Bearer <access_token>` |

## 工具：search_kb

**用途**：对已发布（`published`）条目做混合检索（向量 + BM25）。

**参数**

- `query`（string，必填）：检索词或问句
- `limit`（integer，可选）：1–50，默认 20

**示例**

```bash
curl -G "{search_url}" \\
  -H "Authorization: Bearer YOUR_JWT" \\
  --data-urlencode "q=Transformer 注意力机制" \\
  --data-urlencode "limit=10"
```

**响应字段**

- `items[]`：`item_id`、`title`、`snippet`、`score`、`source_type`、`page`、`tags`

## 使用建议

1. 先调用 `search_kb` 再组织回答，并注明信息来自知识库片段。
2. Token 可在 KnowMind Web 登录后从浏览器本地存储或 `/auth/login` 获取。
3. 也可在 KnowMind「工具与集成」页下载 MCP 配置，在 Cursor 中作为 MCP 工具使用。
"""


def build_mcp_manifest(
    *,
    kb: KnowledgeBase,
    api_base: str,
    mcp_root: str | Path | None = None,
    access_token_placeholder: str = "YOUR_JWT_HERE",
) -> dict[str, Any]:
    root = Path(mcp_root or _DEFAULT_MCP_ROOT).resolve()
    base = api_base.rstrip("/")
    key = _mcp_server_key(kb)
    return {
        "mcpServers": {
            key: {
                "command": "uv",
                "args": [
                    "--directory",
                    str(root),
                    "run",
                    "python",
                    "-m",
                    "kb_search.server",
                ],
                "env": {
                    "KNOWMIND_API_BASE": base,
                    "KNOWMIND_KB_ID": kb.id,
                    "KNOWMIND_ACCESS_TOKEN": access_token_placeholder,
                },
            },
        },
        "_knowmind": {
            "kb_id": kb.id,
            "kb_name": kb.name,
            "api_base": base,
            "instructions": (
                "将 KNOWMIND_ACCESS_TOKEN 替换为你的 JWT；"
                f"若 knowmind-mcp 不在 {root}，请修改 command/args 中的 --directory 路径。"
            ),
        },
    }


def skill_markdown_filename(kb: KnowledgeBase) -> str:
    slug = _slugify(kb.name, fallback="kb")
    safe = re.sub(r"[^a-z0-9-]", "", slug) or f"kb-{kb.id[:8]}"
    return f"knowmind-skill-{safe}.md"


def mcp_manifest_filename(kb: KnowledgeBase) -> str:
    slug = _slugify(kb.name, fallback="kb")
    safe = re.sub(r"[^a-z0-9-]", "", slug) or f"kb-{kb.id[:8]}"
    return f"knowmind-mcp-{safe}.json"


def mcp_manifest_json(*, kb: KnowledgeBase, api_base: str, **kwargs: Any) -> str:
    return json.dumps(build_mcp_manifest(kb=kb, api_base=api_base, **kwargs), ensure_ascii=False, indent=2)
