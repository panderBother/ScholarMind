import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type ReportCitationDto = {
  index: number;
  chunk_id?: string | null;
  item_id?: string | null;
  document_id?: string | null;
  title: string;
  meta?: string | null;
  snippet: string;
  page?: number | null;
  score?: number | null;
};

export type ResearchReportListItemDto = {
  id: string;
  kb_id: string;
  conversation_id: string | null;
  title: string;
  summary: string | null;
  status: string;
  citation_count: number;
  created_at: string;
  updated_at: string;
};

export type ResearchReportDto = {
  id: string;
  kb_id: string;
  conversation_id: string | null;
  title: string;
  summary: string | null;
  content_md: string;
  raw_answer_md: string | null;
  outline: string[];
  citations: ReportCitationDto[];
  status: string;
  created_at: string;
  updated_at: string;
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
    if (typeof j.detail === "string") return j.detail;
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function listReports(kbId?: string): Promise<ResearchReportListItemDto[]> {
  const q = kbId ? `?kb_id=${encodeURIComponent(kbId)}` : "";
  const res = await fetch(`${BASE}/reports${q}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ResearchReportListItemDto[];
}

export async function fetchReport(reportId: string): Promise<ResearchReportDto> {
  const res = await fetch(`${BASE}/reports/${encodeURIComponent(reportId)}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ResearchReportDto;
}

export async function generateReportFromConversation(
  conversationId: string,
  body: { kb_id: string; title?: string },
): Promise<ResearchReportDto> {
  const res = await fetch(`${BASE}/conversations/${encodeURIComponent(conversationId)}/generate-report`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ResearchReportDto;
}

export async function downloadReportMarkdown(reportId: string, filename: string): Promise<void> {
  const res = await fetch(`${BASE}/reports/${encodeURIComponent(reportId)}/export`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename.endsWith(".md") ? filename : `${filename}.md`;
  a.click();
  URL.revokeObjectURL(url);
}

export async function deleteReport(reportId: string): Promise<void> {
  const res = await fetch(`${BASE}/reports/${encodeURIComponent(reportId)}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}
