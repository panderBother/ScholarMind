/**
 * 知识库热度统计 API（`/api/v1/knowledge-bases/{kb_id}/analytics`）。
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type AnalyticsOverviewDto = {
  days: number;
  chat_turns: number;
  search_hits: number;
  rag_cites: number;
  unique_users: number;
  total_events: number;
};

export type TopItemDto = {
  item_id: string;
  title: string;
  count: number;
  search_hits: number;
  rag_cites: number;
};

export type TrendPointDto = {
  date: string;
  search_hit: number;
  rag_cite: number;
  chat_turn: number;
  total: number;
};

export type AnalyticsTrendDto = {
  days: number;
  points: TrendPointDto[];
};

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: string }).message);
    }
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

export async function fetchAnalyticsOverview(
  kbId: string,
  days: 7 | 30 = 7,
): Promise<AnalyticsOverviewDto> {
  const res = await fetch(
    `${BASE}/knowledge-bases/${kbId}/analytics/overview?days=${days}`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AnalyticsOverviewDto;
}

export async function fetchAnalyticsTopItems(
  kbId: string,
  days: 7 | 30 = 7,
  limit = 10,
): Promise<TopItemDto[]> {
  const res = await fetch(
    `${BASE}/knowledge-bases/${kbId}/analytics/top-items?days=${days}&limit=${limit}`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(await parseError(res));
  const body = (await res.json()) as { items: TopItemDto[] };
  return body.items;
}

export async function fetchAnalyticsTrend(
  kbId: string,
  days: 7 | 30 = 7,
): Promise<AnalyticsTrendDto> {
  const res = await fetch(
    `${BASE}/knowledge-bases/${kbId}/analytics/trend?days=${days}`,
    { headers: authHeaders() },
  );
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as AnalyticsTrendDto;
}
