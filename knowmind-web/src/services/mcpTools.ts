/**
 * MCP 工具注册：内置开关 + 外部 mcp.json 导入
 */

import { apiFetch, parseApiError } from "@/services/http";

const PREFIX = "/mcp/tools";

export type McpServerConfig = {
  command?: string | null;
  args: string[];
  env: Record<string, string>;
  headers: Record<string, string>;
  url?: string | null;
  cwd?: string | null;
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

export async function fetchMcpTools(): Promise<McpToolsResponse> {
  const res = await apiFetch(PREFIX);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as McpToolsResponse;
}

export async function setBuiltinMcpEnabled(id: string, enabled: boolean): Promise<McpToolsResponse> {
  const res = await apiFetch(`${PREFIX}/builtin`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, enabled }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as McpToolsResponse;
}

export async function setCustomMcpEnabled(id: string, enabled: boolean): Promise<McpToolsResponse> {
  const res = await apiFetch(`${PREFIX}/custom/${encodeURIComponent(id)}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ id, enabled }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as McpToolsResponse;
}

export async function importMcpJson(rawJson: string): Promise<{
  imported: number;
  skipped: number;
  skip_details: string[];
  custom: CustomMcpTool[];
}> {
  const res = await apiFetch(`${PREFIX}/import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ raw_json: rawJson }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as {
    imported: number;
    skipped: number;
    skip_details: string[];
    custom: CustomMcpTool[];
  };
}

export async function deleteCustomMcp(id: string): Promise<McpToolsResponse> {
  const res = await apiFetch(`${PREFIX}/custom/${encodeURIComponent(id)}`, {
    method: "DELETE",
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as McpToolsResponse;
}

export type UpdateCustomMcpPayload = {
  name: string;
  description?: string;
  enabled: boolean;
  config: McpServerConfig;
};

export async function updateCustomMcp(
  id: string,
  payload: UpdateCustomMcpPayload,
): Promise<McpToolsResponse> {
  const res = await apiFetch(`${PREFIX}/custom/${encodeURIComponent(id)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
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
