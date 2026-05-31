/**
 * 知识库 API（`/api/v1/knowledge-bases`）。
 */

import { apiFetch, parseApiError } from "@/services/http";

export type KnowledgeBaseDto = {
  id: string;
  name: string;
  doc_count: number;
  item_count: number;
  created_at: string;
  updated_at: string;
};

export async function listKnowledgeBases(): Promise<KnowledgeBaseDto[]> {
  const res = await apiFetch(`/knowledge-bases`, { });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as KnowledgeBaseDto[];
}

export async function createKnowledgeBase(name: string): Promise<KnowledgeBaseDto> {
  const res = await apiFetch(`/knowledge-bases`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as KnowledgeBaseDto;
}

export async function updateKnowledgeBase(id: string, name: string): Promise<KnowledgeBaseDto> {
  const res = await apiFetch(`/knowledge-bases/${id}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as KnowledgeBaseDto;
}

export async function deleteKnowledgeBase(id: string): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${id}`, {
    method: "DELETE",
    });
  if (!res.ok) throw new Error(await parseApiError(res));
}
