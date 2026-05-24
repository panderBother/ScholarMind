import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

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

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return { Authorization: `Bearer ${token}` };
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

  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/search?${sp}`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as SearchResultDto;
}
