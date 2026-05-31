import { getAccessToken } from "@/services/auth";
import { apiFetch, parseApiError } from "@/services/http";

export type DocumentDto = {
  id: string;
  kb_id: string;
  filename: string;
  file_type: string | null;
  status: string;
  chunk_count: number;
  file_bytes: number;
  md5: string | null;
  title: string | null;
  parsed_title: string | null;
  parsed_summary: string | null;
  parse_progress: number;
  parse_stage: string | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
};

export type DocumentUploadResult = {
  documents: DocumentDto[];
  skipped_duplicates: number;
  needs_preview: string[];
};

export type DocumentParsedContentDto = {
  doc_id: string;
  filename: string;
  file_type: string | null;
  title: string | null;
  summary: string | null;
  content: string;
  status: string;
};

export const SUPPORTED_UPLOAD_ACCEPT =
  ".pdf,.docx,.doc,.xlsx,.xls,.csv,.md,.markdown,.txt,.png,.jpg,.jpeg,.webp";

const API = "/api/v1";

async function parseError(res: Response): Promise<string> {
  return parseApiError(res);
}

async function parseXhrError(xhr: XMLHttpRequest): Promise<string> {
  try {
    const j = JSON.parse(xhr.responseText) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    return xhr.statusText || "上传失败";
  } catch {
    return xhr.statusText || "上传失败";
  }
}

export async function listDocuments(kbId: string): Promise<DocumentDto[]> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents`);
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentDto[];
}

export async function retryDocumentParse(kbId: string, docId: string): Promise<DocumentDto> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}/retry-parse`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentDto;
}

export async function uploadDocuments(kbId: string, files: File[]): Promise<DocumentUploadResult> {
  return uploadDocumentsWithProgress(kbId, files);
}

export function uploadDocumentsWithProgress(
  kbId: string,
  files: File[],
  onProgress?: (percent: number) => void,
): Promise<DocumentUploadResult> {
  return new Promise((resolve, reject) => {
    const token = getAccessToken();
    if (!token) {
      reject(new Error("未登录"));
      return;
    }
    const xhr = new XMLHttpRequest();
    const fd = new FormData();
    for (const f of files) {
      fd.append("files", f);
    }
    xhr.upload.addEventListener("progress", (e) => {
      if (e.lengthComputable && onProgress) {
        onProgress(Math.min(100, Math.round((e.loaded / e.total) * 100)));
      }
    });
    xhr.addEventListener("load", () => {
      if (xhr.status >= 200 && xhr.status < 300) {
        try {
          resolve(JSON.parse(xhr.responseText) as DocumentUploadResult);
        } catch {
          reject(new Error("响应解析失败"));
        }
        return;
      }
      void parseXhrError(xhr).then(reject);
    });
    xhr.addEventListener("error", () => reject(new Error("网络错误，上传失败")));
    xhr.addEventListener("abort", () => reject(new Error("上传已取消")));
    xhr.open("POST", `${API}/knowledge-bases/${kbId}/documents`);
    xhr.setRequestHeader("Authorization", `Bearer ${token}`);
    xhr.send(fd);
  });
}

export async function deleteDocument(kbId: string, docId: string): Promise<void> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseError(res));
}

export async function getDocument(kbId: string, docId: string): Promise<DocumentDto> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}`);
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentDto;
}

export async function getDocumentParsedContent(
  kbId: string,
  docId: string,
): Promise<DocumentParsedContentDto> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}/parsed-content`);
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentParsedContentDto;
}

export async function updateDocumentParsedContent(
  kbId: string,
  docId: string,
  body: { title?: string | null; summary?: string | null; content: string },
): Promise<DocumentParsedContentDto> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}/parsed-content`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as DocumentParsedContentDto;
}

export async function confirmDocumentImport(
  kbId: string,
  docId: string,
): Promise<{ document: DocumentDto }> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}/confirm-import`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as { document: DocumentDto };
}

/** 带鉴权拉取原始文件，用于 iframe / object 预览 */
export async function fetchDocumentFileBlob(kbId: string, docId: string): Promise<Blob> {
  const res = await apiFetch(`/knowledge-bases/${kbId}/documents/${docId}/file`);
  if (!res.ok) throw new Error(await parseError(res));
  return res.blob();
}

/** @deprecated 使用 fetchDocumentFileBlob */
export const fetchDocumentPdfBlob = fetchDocumentFileBlob;

export function isPdfDocument(doc: DocumentDto): boolean {
  return (doc.file_type || doc.filename.split(".").pop()?.toLowerCase()) === "pdf";
}

export function needsPreview(doc: DocumentDto): boolean {
  return doc.status === "preview";
}

export function documentParseProgress(doc: DocumentDto): number {
  if (doc.status === "done") return 100;
  if (doc.status === "preview") return doc.parse_progress ?? 100;
  if (doc.status === "pending" || doc.status === "processing") {
    return doc.parse_progress ?? (doc.status === "pending" ? 5 : 10);
  }
  return 0;
}

export function documentParseStageLabel(doc: DocumentDto): string | null {
  if (doc.parse_stage) return doc.parse_stage;
  if (doc.status === "pending") return "排队中";
  if (doc.status === "processing") return "解析中";
  if (doc.status === "preview") return "待确认";
  return null;
}

export function filterSupportedFiles(files: FileList | File[]): File[] {
  const exts = SUPPORTED_UPLOAD_ACCEPT.split(",").map((e) => e.trim().toLowerCase());
  return Array.from(files).filter((f) => exts.some((ext) => f.name.toLowerCase().endsWith(ext)));
}
