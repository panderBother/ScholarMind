/**
 * 知识库 API（`/api/v1/knowledge-bases`）。
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type KnowledgeBaseDto = {
  id: string;
  name: string;
  doc_count: number;
  created_at: string;
  updated_at: string;
};

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: string }).message);
    }
    if (Array.isArray(d)) return d.map((x) => JSON.stringify(x)).join("; ");
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return { Authorization: `Bearer ${token}` };
}

export async function listKnowledgeBases(): Promise<KnowledgeBaseDto[]> {
  const res = await fetch(`${BASE}/knowledge-bases`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeBaseDto[];
}

export async function createKnowledgeBase(name: string): Promise<KnowledgeBaseDto> {
  const res = await fetch(`${BASE}/knowledge-bases`, {
    method: "POST",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeBaseDto;
}

export async function updateKnowledgeBase(id: string, name: string): Promise<KnowledgeBaseDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${id}`, {
    method: "PATCH",
    headers: { ...authHeaders(), "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeBaseDto;
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  const res = await fetch(`${BASE}/knowledge-bases/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
