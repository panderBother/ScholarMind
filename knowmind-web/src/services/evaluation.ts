/**
 * RAG 评估看板 API（`/api/v1/evaluation/dashboard`）。
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type EvalKpiDto = {
  value: number;
  delta: number;
};

export type EvalTrendPointDto = {
  label: string;
  faithfulness: number;
  answer_relevancy: number;
  context_recall: number;
  context_precision: number;
};

export type EvalVersionCompareDto = {
  name: string;
  current: number;
  baseline: number;
};

export type EvalDashboardDto = {
  run_id: string | null;
  created_at: string | null;
  version: string | null;
  mode: string;
  sample_count: number;
  kpis: Record<string, EvalKpiDto>;
  trend: EvalTrendPointDto[];
  version_compare: EvalVersionCompareDto[];
  stats: {
    total_runs: number;
    question_count: number;
    avg_latency_s: number;
    pass_rate: number;
  };
};

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

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  return { Authorization: `Bearer ${token}` };
}

export async function fetchEvalDashboard(): Promise<EvalDashboardDto> {
  const res = await fetch(`${BASE}/evaluation/dashboard`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as EvalDashboardDto;
}
