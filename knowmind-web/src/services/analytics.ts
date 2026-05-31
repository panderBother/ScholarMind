/**
 * 知识库热度统计 API（`/api/v1/knowledge-bases/{kb_id}/analytics`）。
 */

import { apiFetch, parseApiError } from "@/services/http";
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

export async function fetchAnalyticsOverview(
  kbId: string,
  days: 7 | 30 = 7,
): Promise<AnalyticsOverviewDto> {
  const res = await apiFetch(
    `/knowledge-bases/${kbId}/analytics/overview?days=${days}`,
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as AnalyticsOverviewDto;
}

export async function fetchAnalyticsTopItems(
  kbId: string,
  days: 7 | 30 = 7,
  limit = 10,
): Promise<TopItemDto[]> {
  const res = await apiFetch(
    `/knowledge-bases/${kbId}/analytics/top-items?days=${days}&limit=${limit}`,
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  const body = (await res.json()) as { items: TopItemDto[] };
  return body.items;
}

export async function fetchAnalyticsTrend(
  kbId: string,
  days: 7 | 30 = 7,
): Promise<AnalyticsTrendDto> {
  const res = await apiFetch(
    `/knowledge-bases/${kbId}/analytics/trend?days=${days}`,
  );
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as AnalyticsTrendDto;
}
