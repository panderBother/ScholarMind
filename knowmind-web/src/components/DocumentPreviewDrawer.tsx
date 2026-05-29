import { useEffect, useMemo, useState } from "react";
import { ExternalLink, FileText, Pencil, Trash2 } from "lucide-react";

import {
  fetchDocumentFileBlob,
  isPdfDocument,
  type DocumentDto,
} from "@/services/documents";

type Props = {
  kbId: string;
  doc: DocumentDto;
  initialPage?: number | null;
  onClose: () => void;
  onEditItems: (doc: DocumentDto) => void;
  onDelete?: (doc: DocumentDto) => void;
};

/** 文档视图：仅预览原文件（PDF / 图片等），不在此编辑识别正文。 */
export function DocumentPreviewDrawer({ kbId, doc, initialPage, onClose, onEditItems, onDelete }: Props) {
  const [fileUrl, setFileUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const isPdf = isPdfDocument(doc);

  const pdfViewerSrc = useMemo(() => {
    if (!fileUrl || !isPdf) return null;
    if (initialPage != null && initialPage >= 0) {
      return `${fileUrl}#page=${initialPage + 1}`;
    }
    return fileUrl;
  }, [fileUrl, initialPage, isPdf]);

  useEffect(() => {
    let objectUrl: string | null = null;
    let cancelled = false;
    setLoading(true);
    setErr(null);
    setFileUrl(null);
    void (async () => {
      try {
        if (doc.status !== "done") {
          setErr("文档尚未解析完成，暂无法预览原文件");
          return;
        }
        const blob = await fetchDocumentFileBlob(kbId, doc.id);
        if (cancelled) return;
        if (blob.type.startsWith("image/") || isPdf || blob.type === "application/pdf") {
          objectUrl = URL.createObjectURL(blob);
          setFileUrl(objectUrl);
        } else {
          setErr("该格式请下载原文件查看；识别正文请在「条目视图」编辑。");
        }
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "加载预览失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [kbId, doc.id, doc.status, isPdf]);

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
              {mb} MB · 语义检索 {doc.chunk_count} 段 · {doc.title || "无提取标题"}
              {initialPage != null && initialPage >= 0 ? ` · 定位第 ${initialPage + 1} 页` : ""}
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            {doc.status === "done" ? (
              <button
                type="button"
                onClick={() => onEditItems(doc)}
                className="inline-flex items-center gap-1 rounded-lg border border-primary/30 bg-primary-soft px-3 py-1.5 text-sm font-semibold text-primary hover:bg-primary-soft/80"
              >
                <Pencil className="h-4 w-4" />
                去条目视图编辑
              </button>
            ) : null}
            {onDelete ? (
              <button
                type="button"
                onClick={() => onDelete(doc)}
                className="inline-flex items-center gap-1 rounded-lg border border-red-200 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50"
              >
                <Trash2 className="h-4 w-4" />
                删除文档
              </button>
            ) : null}
            {pdfViewerSrc ? (
              <a
                href={pdfViewerSrc}
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
          <p className="flex flex-1 items-center justify-center text-sm text-slate-500">加载原文件…</p>
        ) : pdfViewerSrc ? (
          <iframe title={doc.filename} src={pdfViewerSrc} className="min-h-0 flex-1 w-full border-0 bg-slate-100" />
        ) : fileUrl ? (
          <img src={fileUrl} alt={doc.filename} className="mx-auto max-h-full max-w-full object-contain p-4" />
        ) : (
          <p className="flex flex-1 items-center justify-center text-sm text-slate-500">无法预览</p>
        )}
      </div>
    </div>
  );
}
