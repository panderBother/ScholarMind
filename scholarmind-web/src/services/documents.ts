import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type DocumentDto = {
  id: string;
  kb_id: string;
  filename: string;
  status: string;
  chunk_count: number;
  file_bytes: number;
  md5: string | null;
  title: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentUploadResult = {
  documents: DocumentDto[];
  skipped_duplicates: number;
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
    if (d && typeof d === "object" && "message" in d) {
      return String((d as { message: string }).message);
    }
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function listDocuments(kbId: string): Promise<DocumentDto[]> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/documents`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentDto[];
}

export async function retryDocumentParse(kbId: string, docId: string): Promise<DocumentDto> {
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/documents/${docId}/retry-parse`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentDto;
}

export async function uploadDocuments(kbId: string, files: File[]): Promise<DocumentUploadResult> {
  const fd = new FormData();
  for (const f of files) {
    fd.append("files", f);
  }
  const res = await fetch(`${BASE}/knowledge-bases/${kbId}/documents`, {
    method: "POST",
    headers: authHeaders(),
    body: fd,
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentUploadResult;
}
