/**
 * 知识库 Skill / MCP 导出
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

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
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: string }).message);
    }
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

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
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/export/skill`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), "knowmind-skill.md");
  downloadBlob(blob, name);
}

export async function downloadSkillJson(kbId: string): Promise<void> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/export/skill?format=json`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const data = (await res.json()) as SkillExportJsonDto;
  const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
  downloadBlob(blob, `knowmind-skill-${kbId.slice(0, 8)}.json`);
}

export async function downloadMcpManifest(kbId: string): Promise<void> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/export/mcp-manifest`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  const blob = await res.blob();
  const name = filenameFromDisposition(res.headers.get("Content-Disposition"), "knowmind-mcp.json");
  downloadBlob(blob, name);
}

export async function fetchSkillJson(kbId: string): Promise<SkillExportJsonDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/export/skill?format=json`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as SkillExportJsonDto;
}
