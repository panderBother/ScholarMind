import { useEffect, useState } from "react";
import { ExternalLink, FileText, Pencil, Trash2 } from "lucide-react";

import { fetchDocumentPdfBlob, type DocumentDto } from "@/services/documents";

type Props = {
  kbId: string;
  doc: DocumentDto;
  onClose: () => void;
  onEditItems: (doc: DocumentDto) => void;
  onDelete?: (doc: DocumentDto) => void;
};

export function DocumentPreviewDrawer({ kbId, doc, onClose, onEditItems, onDelete }: Props) {
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    void (async () => {
      try {
        if (doc.status !== "done") {
          setErr("文献尚未解析完成，暂无法预览 PDF");
          return;
        }
        const blob = await fetchDocumentPdfBlob(kbId, doc.id);
        if (cancelled) return;
        objectUrl = URL.createObjectURL(blob);
        setPdfUrl(objectUrl);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "加载 PDF 失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [kbId, doc.id, doc.status]);

  const mb = (doc.file_bytes / (1024 * 1024)).toFixed(2);

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40" onClick={onClose}>
      <div
        className="flex h-full w-full max-w-4xl flex-col bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-3">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <FileText className="h-5 w-5 shrink-0 text-red-500" />
              <h2 className="truncate font-semibold text-slate-900">{doc.filename}</h2>
            </div>
            <p className="mt-1 text-xs text-slate-500">
              {mb} MB · {doc.chunk_count} 个解析块 · {doc.title || "无提取标题"}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {doc.status === "done" ? (
              <button
                type="button"
                onClick={() => onEditItems(doc)}
                className="inline-flex items-center gap-1 rounded-lg bg-primary px-3 py-1.5 text-sm font-semibold text-white hover:bg-primary-hover"
              >
                <Pencil className="h-4 w-4" />
                编辑解析条目
              </button>
            ) : null}
            {onDelete ? (
              <button
                type="button"
                onClick={() => onDelete(doc)}
                className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
                删除文献
              </button>
            ) : null}
            {pdfUrl ? (
              <a
                href={pdfUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" />
                新窗口打开
              </a>
            ) : null}
            <button type="button" onClick={onClose} className="rounded-lg px-3 py-1.5 text-sm text-slate-500">
              关闭
            </button>
          </div>
        </div>

        {err ? (
          <p className="bg-amber-50 px-4 py-3 text-sm text-amber-900">{err}</p>
        ) : loading ? (
          <p className="flex flex-1 items-center justify-center text-sm text-slate-500">加载 PDF…</p>
        ) : pdfUrl ? (
          <iframe title={doc.filename} src={pdfUrl} className="min-h-0 flex-1 w-full border-0 bg-slate-100" />
        ) : (
          <p className="flex flex-1 items-center justify-center text-sm text-slate-500">无法预览</p>
        )}
      </div>
    </div>
  );
}
