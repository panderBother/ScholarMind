/**
 * MCP 工具注册：内置开关 + 外部 mcp.json 导入
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1/mcp/tools";

export type McpServerConfig = {
  command?: string | null;
  args: string[];
  env: Record<string, string>;
  url?: string | null;
};

export type BuiltinMcpTool = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  available: boolean;
  kind: "builtin";
};

export type CustomMcpTool = {
  id: string;
  name: string;
  description: string;
  enabled: boolean;
  source: string;
  config: McpServerConfig;
  imported_at: string;
};

export type McpToolsResponse = {
  builtin: BuiltinMcpTool[];
  custom: CustomMcpTool[];
};

async function authHeaders(): Promise<HeadersInit> {
  const token = getAccessToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    if (typeof j.detail === "string") return j.detail;
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function fetchMcpTools(): Promise<McpToolsResponse> {
  const res = await fetch(BASE, { headers: await authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as McpToolsResponse;
}

export async function setBuiltinMcpEnabled(id: string, enabled: boolean): Promise<McpToolsResponse> {
  const res = await fetch(`${BASE}/builtin`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify({ id, enabled }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as McpToolsResponse;
}

export async function setCustomMcpEnabled(id: string, enabled: boolean): Promise<McpToolsResponse> {
  const res = await fetch(`${BASE}/custom/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: await authHeaders(),
    body: JSON.stringify({ id, enabled }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as McpToolsResponse;
}

export async function importMcpJson(rawJson: string): Promise<{
  imported: number;
  skipped: number;
  custom: CustomMcpTool[];
}> {
  const res = await fetch(`${BASE}/import`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ raw_json: rawJson }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as { imported: number; skipped: number; custom: CustomMcpTool[] };
}

export async function deleteCustomMcp(id: string): Promise<McpToolsResponse> {
  const res = await fetch(`${BASE}/custom/${encodeURIComponent(id)}`, {
    method: "DELETE",
    headers: await authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as McpToolsResponse;
}

/** 对话页：是否启用文件读写（与工具页 file_writer 开关联动） */
export async function fetchFileWriterEnabled(): Promise<boolean> {
  try {
    const data = await fetchMcpTools();
    return data.builtin.find((t) => t.id === "file_writer")?.enabled ?? false;
  } catch {
    return false;
  }
}

export async function fetchWebSearchEnabled(): Promise<boolean> {
  try {
    const data = await fetchMcpTools();
    return data.builtin.find((t) => t.id === "web_search")?.enabled ?? false;
  } catch {
    return false;
  }
}
