import { apiFetch, parseApiError } from "@/services/http";
export type SearchHitDto = {
  item_id: string;
  title: string;
  snippet: string;
  score: number;
  source_type: string;
  page: number | null;
  tags: string[];
};

export type SearchResultDto = {
  query: string;
  total: number;
  items: SearchHitDto[];
};

export async function searchKnowledgeBase(
  kbId: string,
  params: {
    q: string;
    limit?: number;
    categoryId?: string;
    tags?: string[];
  },
): Promise<SearchResultDto> {
  const sp = new URLSearchParams();
  sp.set("q", params.q);
  if (params.limit != null) sp.set("limit", String(params.limit));
  if (params.categoryId) sp.set("category_id", params.categoryId);
  if (params.tags?.length) sp.set("tags", params.tags.join(","));

  const res = await apiFetch(`/knowledge-bases/${kbId}/search?${sp}`, {
    });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as SearchResultDto;
}
