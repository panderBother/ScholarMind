import { useState } from "react";

import { MarkdownPreview } from "@/components/MarkdownPreview";
import { importUrlItem, previewUrlItem, type UrlImportPreviewDto } from "@/services/distill";

type Props = {
  kbId: string;
  categories: { id: string; label: string }[];
  onClose: () => void;
  onImported: () => void;
};

export function UrlImportModal({ kbId, categories, onClose, onImported }: Props) {
  const [url, setUrl] = useState("");
  const [categoryId, setCategoryId] = useState(categories[0]?.id ?? "");
  const [publish, setPublish] = useState(true);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [step, setStep] = useState<"form" | "preview">("form");
  const [preview, setPreview] = useState<UrlImportPreviewDto | null>(null);

  const normalizeUrl = (raw: string) => {
    let normalized = raw.trim();
    if (!normalized) return "";
    if (!/^https?:\/\//i.test(normalized)) {
      normalized = `https://${normalized.replace(/^\/+/, "")}`;
    }
    return normalized;
  };

  const onPreview = async () => {
    const normalized = normalizeUrl(url);
    if (!normalized || !categoryId) return;
    setLoading(true);
    setErr(null);
    try {
      const data = await previewUrlItem(kbId, normalized);
      setPreview(data);
      setStep("preview");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "预览失败");
    } finally {
      setLoading(false);
    }
  };

  const onConfirmImport = async () => {
    if (!preview || !categoryId) return;
    setLoading(true);
    setErr(null);
    try {
      await importUrlItem(kbId, {
        url: preview.url,
        category_id: categoryId,
        publish,
        title: preview.title,
        content: preview.content,
        summary: preview.summary,
      });
      onImported();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "入库失败");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4">
      <div
        className={
          step === "preview"
            ? "flex max-h-[92vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
            : "flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl bg-white shadow-xl"
        }
      >
        <div className="border-b px-5 py-4">
          <h2 className="text-lg font-semibold text-slate-900">URL 网页采集</h2>
          <p className="mt-1 text-xs text-slate-500">
            {step === "form"
              ? "采集后先预览 Markdown 正文（仅去除 Copyright / 备案号等页脚噪声）"
              : "Markdown 预览 · 正文与原文基本一致 · 确认后入库且不可再编辑"}
          </p>
        </div>
        {err ? <p className="bg-red-50 px-5 py-2 text-sm text-red-700">{err}</p> : null}
        {step === "form" ? (
          <div className="space-y-3 overflow-y-auto px-5 py-4">
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://www.runoob.com/..."
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-slate-600">
              <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
              入库后立即发布（可检索）
            </label>
          </div>
        ) : preview ? (
          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            <div className="shrink-0 border-b border-slate-100 bg-slate-50/80 px-5 py-3">
              <p className="text-sm font-medium text-slate-900">{preview.title}</p>
              {preview.page_title ? (
                <p className="mt-0.5 text-xs text-slate-500">原网页标题：{preview.page_title}</p>
              ) : null}
              {preview.summary ? (
                <p className="mt-2 text-xs leading-relaxed text-slate-600">{preview.summary}</p>
              ) : null}
              <p className="mt-2 text-xs text-slate-400">共 {preview.content.length.toLocaleString()} 字</p>
            </div>
            <div className="min-h-0 flex-1 overflow-y-auto px-5 py-4">
              <p className="mb-2 text-xs font-medium text-slate-500">Markdown 预览</p>
              <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-inner">
                <MarkdownPreview markdown={preview.content} />
              </div>
            </div>
          </div>
        ) : null}
        <div className="flex justify-end gap-2 border-t px-5 py-4">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-600">
            取消
          </button>
          {step === "form" ? (
            <button
              type="button"
              disabled={loading || !url.trim()}
              onClick={() => void onPreview()}
              className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loading ? "采集中…" : "采集预览"}
            </button>
          ) : (
            <>
              <button
                type="button"
                disabled={loading}
                onClick={() => {
                  setStep("form");
                  setPreview(null);
                  setErr(null);
                }}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700"
              >
                返回修改
              </button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void onConfirmImport()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
              >
                {loading ? "入库中…" : "确认入库"}
              </button>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
