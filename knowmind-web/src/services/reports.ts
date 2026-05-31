import { apiFetch, parseApiError } from "@/services/http";

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

export async function listReports(kbId?: string): Promise<ResearchReportListItemDto[]> {
  const q = kbId ? `?kb_id=${encodeURIComponent(kbId)}` : "";
  const res = await apiFetch(`/reports${q}`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ResearchReportListItemDto[];
}

export async function fetchReport(reportId: string): Promise<ResearchReportDto> {
  const res = await apiFetch(`/reports/${encodeURIComponent(reportId)}`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ResearchReportDto;
}

export async function generateReportFromConversation(
  conversationId: string,
  body: { kb_id: string; title?: string },
): Promise<ResearchReportDto> {
  const res = await apiFetch(`/conversations/${encodeURIComponent(conversationId)}/generate-report`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ResearchReportDto;
}

async function downloadBlob(path: string, filename: string): Promise<void> {
  const res = await apiFetch(path);
  if (!res.ok) throw new Error(await parseApiError(res));
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export async function downloadReportMarkdown(reportId: string, filename: string): Promise<void> {
  const name = filename.endsWith(".md") ? filename : `${filename}.md`;
  await downloadBlob(`/reports/${encodeURIComponent(reportId)}/export`, name);
}

export async function downloadReportPdf(reportId: string, filename: string): Promise<void> {
  const name = filename.endsWith(".pdf") ? filename : `${filename}.pdf`;
  await downloadBlob(`/reports/${encodeURIComponent(reportId)}/export.pdf`, name);
}

export async function deleteReport(reportId: string): Promise<void> {
  const res = await apiFetch(`/reports/${encodeURIComponent(reportId)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseApiError(res));
}
