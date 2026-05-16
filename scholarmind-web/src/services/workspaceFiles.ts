/**
 * 受控文件工作区 API（需登录）。
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1/workspace/files";

export type AllowedRootsResponse = {
  allowed_roots: string[];
  hint_env: string;
};

export type FileReadResponse = {
  path: string | null;
  content: string | null;
  status: string;
  truncated?: boolean;
  size_bytes?: number;
};

export type FileWriteResponse = {
  path: string | null;
  status: string;
  bytes_written?: number;
};

async function authHeaders(): Promise<HeadersInit> {
  const token = getAccessToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

export async function fetchAllowedRoots(): Promise<AllowedRootsResponse> {
  const res = await fetch(`${BASE}/roots`, { headers: await authHeaders() });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as AllowedRootsResponse;
}

export async function readWorkspaceFile(path: string): Promise<FileReadResponse> {
  const res = await fetch(`${BASE}/read`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({ path }),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as FileReadResponse;
}

export async function writeWorkspaceFile(
  path: string,
  content: string,
  options?: { format?: "auto" | "markdown" | "text"; overwrite?: boolean },
): Promise<FileWriteResponse> {
  const res = await fetch(`${BASE}/write`, {
    method: "POST",
    headers: await authHeaders(),
    body: JSON.stringify({
      path,
      content,
      format: options?.format ?? "auto",
      overwrite: options?.overwrite ?? true,
    }),
  });
  if (!res.ok) throw new Error(await res.text());
  return (await res.json()) as FileWriteResponse;
}
