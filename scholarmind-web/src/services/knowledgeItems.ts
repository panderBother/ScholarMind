import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type KnowledgeItemDto = {
  id: string;
  kb_id: string;
  document_id: string | null;
  category_id: string | null;
  source_type: string;
  title: string;
  content: string;
  summary: string | null;
  tags: string[] | null;
  lifecycle_status: string;
  access_level: string;
  source: string | null;
  chunk_id: string | null;
  page: number | null;
  published_at: string | null;
  created_at: string;
  updated_at: string;
};

export type KnowledgeItemCreatePayload = {
  title: string;
  content: string;
  category_id: string;
  summary?: string;
  tags?: string[];
  access_level?: string;
  source?: string;
  publish?: boolean;
};

export type KnowledgeItemUpdatePayload = {
  title?: string;
  content?: string;
  category_id?: string;
  summary?: string;
  tags?: string[];
  access_level?: string;
  source?: string;
};

function authHeaders(json = false): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  const h: HeadersInit = { Authorization: `Bearer ${token}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function getKnowledgeItem(kbId: string, itemId: string): Promise<KnowledgeItemDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items/${itemId}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeItemDto;
}

export async function listKnowledgeItems(
  kbId: string,
  params?: {
    lifecycle_status?: string;
    category_id?: string;
    source_type?: string;
    document_id?: string;
    q?: string;
  },
): Promise<KnowledgeItemDto[]> {
  const qs = new URLSearchParams();
  if (params?.lifecycle_status) qs.set("lifecycle_status", params.lifecycle_status);
  if (params?.category_id) qs.set("category_id", params.category_id);
  if (params?.source_type) qs.set("source_type", params.source_type);
  if (params?.document_id) qs.set("document_id", params.document_id);
  if (params?.q) qs.set("q", params.q);
  const suffix = qs.toString() ? `?${qs.toString()}` : "";
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items${suffix}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeItemDto[];
}

export async function createKnowledgeItem(
  kbId: string,
  body: KnowledgeItemCreatePayload,
): Promise<KnowledgeItemDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeItemDto;
}

export async function updateKnowledgeItem(
  kbId: string,
  itemId: string,
  body: KnowledgeItemUpdatePayload,
): Promise<KnowledgeItemDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items/${itemId}`, {
    method: "PATCH",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeItemDto;
}

export async function publishKnowledgeItem(kbId: string, itemId: string): Promise<KnowledgeItemDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items/${itemId}/publish`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeItemDto;
}

export async function archiveKnowledgeItem(kbId: string, itemId: string): Promise<KnowledgeItemDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items/${itemId}/archive`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as KnowledgeItemDto;
}

export async function deleteKnowledgeItem(kbId: string, itemId: string): Promise<void> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/items/${itemId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
