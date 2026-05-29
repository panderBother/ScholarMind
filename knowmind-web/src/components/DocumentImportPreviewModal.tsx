import { useEffect, useState } from "react";
import { Eye, Pencil } from "lucide-react";

import { MarkdownPreview } from "@/components/MarkdownPreview";
import {
  confirmDocumentImport,
  getDocumentParsedContent,
  updateDocumentParsedContent,
  type DocumentDto,
  type DocumentParsedContentDto,
} from "@/services/documents";

type Props = {
  kbId: string;
  doc: DocumentDto;
  onClose: () => void;
  onConfirmed: () => void;
};

export function DocumentImportPreviewModal({ kbId, doc, onClose, onConfirmed }: Props) {
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [mode, setMode] = useState<"edit" | "preview">("edit");
  const [parsed, setParsed] = useState<DocumentParsedContentDto | null>(null);
  const [title, setTitle] = useState("");
  const [summary, setSummary] = useState("");
  const [content, setContent] = useState("");

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    void (async () => {
      try {
        const data = await getDocumentParsedContent(kbId, doc.id);
        if (cancelled) return;
        setParsed(data);
        setTitle(data.title ?? "");
        setSummary(data.summary ?? "");
        setContent(data.content);
      } catch (e) {
        if (!cancelled) setErr(e instanceof Error ? e.message : "加载预览失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [kbId, doc.id]);

  const onSaveDraft = async () => {
    if (!content.trim()) {
      setErr("内容不能为空");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const data = await updateDocumentParsedContent(kbId, doc.id, {
        title: title.trim() || null,
        summary: summary.trim() || null,
        content: content.trim(),
      });
      setParsed(data);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const onConfirm = async () => {
    if (!content.trim()) {
      setErr("内容不能为空");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      await updateDocumentParsedContent(kbId, doc.id, {
        title: title.trim() || null,
        summary: summary.trim() || null,
        content: content.trim(),
      });
      await confirmDocumentImport(kbId, doc.id);
      onConfirmed();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "入库失败");
    } finally {
      setSaving(false);
    }
  };

  const fileTypeLabel = parsed?.file_type || doc.file_type || "文件";

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div className="flex max-h-[92vh] w-full max-w-5xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="border-b px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-900">解析预览 · {doc.filename}</h2>
          <p className="mt-1 text-xs text-slate-500">
            格式：{fileTypeLabel} · 确认入库前可编辑标题、摘要与正文（Markdown）
          </p>
        </div>
        {err ? <p className="bg-red-50 px-5 py-2 text-sm text-red-700">{err}</p> : null}
        {loading ? (
          <p className="flex flex-1 items-center justify-center px-5 py-12 text-sm text-slate-500">
            加载解析结果…
          </p>
        ) : (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="shrink-0 space-y-3 border-b border-slate-100 px-5 py-4">
              <input
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="标题"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm font-medium"
              />
              <input
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="摘要（可选）"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <p className="text-xs text-slate-400">共 {content.length.toLocaleString()} 字</p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              {mode === "edit" ? (
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  className="h-full min-h-[320px] w-full resize-y rounded-xl border border-slate-200 p-4 font-mono text-sm leading-relaxed text-slate-800"
                  spellCheck={false}
                />
              ) : (
                <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-inner">
                  <MarkdownPreview markdown={content} />
                </div>
              )}
            </div>
          </div>
        )}
        <div className="flex flex-wrap items-center justify-end gap-2 border-t px-5 py-4">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-600">
            取消
          </button>
          {!loading ? (
            <>
              <button
                type="button"
                disabled={saving}
                onClick={() => setMode((m) => (m === "edit" ? "preview" : "edit"))}
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700"
              >
                {mode === "edit" ? <Eye className="h-4 w-4" /> : <Pencil className="h-4 w-4" />}
                {mode === "edit" ? "Markdown 预览" : "返回编辑"}
              </button>
              <button
                type="button"
                disabled={saving}
                onClick={() => void onSaveDraft()}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 disabled:opacity-50"
              >
                {saving ? "保存中…" : "保存草稿"}
              </button>
              <button
                type="button"
                disabled={saving || !content.trim()}
                onClick={() => void onConfirm()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {saving ? "入库中…" : "确认入库"}
              </button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
