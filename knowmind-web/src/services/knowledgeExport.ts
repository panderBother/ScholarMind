/**
 * 知识库 Skill / MCP 导出
 */

import { apiFetch, parseApiError } from "@/services/http";
function filenameFromDisposition(header: string | null, fallback: string): string {
  if (!header) return fallback;
  const m = /filename="([^"]+)"/i.exec(header);
  return m?.[1] ?? fallback;
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export type SkillExportJsonDto = {
  name: string;
  description: string;
  parameters: Record<string, unknown>;
  kb_id: string;
  kb_name: string;
  api_base: string;
  endpoint: string;
  auth: string;
};

export async function downloadSkillMarkdown(kbId: string): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/export/skill`, {
    });
  if (!res.ok) throw new Error(await parseApiError(res));
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), "knowmind-skill.md");
  downloadBlob(blob, name);
}

export async function downloadSkillJson(kbId: string): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/export/skill?format=json`, {
    });
  if (!res.ok) throw new Error(await parseApiError(res));
  const data = (await res.json()) as SkillExportJsonDto;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  downloadBlob(blob, `knowmind-skill-${kbId.slice(0, 8)}.json`);
}

export async function downloadMcpManifest(kbId: string): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/export/mcp-manifest`, {
    });
  if (!res.ok) throw new Error(await parseApiError(res));
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), "knowmind-mcp.json");
  downloadBlob(blob, name);
}

export async function fetchSkillJson(kbId: string): Promise<SkillExportJsonDto> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/export/skill?format=json`, {
    });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as SkillExportJsonDto;
}
