import { useState } from "react";
import { Loader2 } from "lucide-react";

import { MarkdownPreview } from "@/components/MarkdownPreview";
import { importUrlItem, previewUrlItem, type UrlImportPreviewDto } from "@/services/distill";

export type UrlImportCategory = { id: string; label: string };

type Props = {
  kbId: string;
  categories: UrlImportCategory[];
  onImported: () => void;
  /** inline：知识生产页；modal 由 UrlImportModal 包一层 */
  layout?: "inline" | "compact";
};

export function UrlImportPanel({ kbId, categories, onImported, layout = "inline" }: Props) {
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
    if (!normalized || !categoryId) {
      setErr("请填写 URL 并选择分类");
      return;
    }
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
      setUrl("");
      setPreview(null);
      setStep("form");
      onImported();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "入库失败");
    } finally {
      setLoading(false);
    }
  };

  if (!categories.length) {
    return (
      <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-8 text-center text-sm text-slate-500">
        请先在条目视图中创建至少一个分类，再进行 URL 采集。
      </p>
    );
  }

  const compact = layout === "compact";

  return (
    <div className={compact ? "space-y-4" : "rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:p-6"}>
      {!compact ? (
        <div className="mb-4">
          <h2 className="text-sm font-semibold text-slate-900">URL 网页采集</h2>
          <p className="mt-1 text-xs leading-relaxed text-slate-500">
            输入公开网页地址，自动抓取正文并转为 Markdown 条目；支持预览后确认入库。
          </p>
        </div>
      ) : null}

      {err ? <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p> : null}

      {step === "form" ? (
        <div className="space-y-3">
          <label className="block text-xs font-medium text-slate-600">
            网页 URL
            <input
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/article"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
            />
          </label>
          <label className="block text-xs font-medium text-slate-600">
            入库分类
            <select
              value={categoryId}
              onChange={(e) => setCategoryId(e.target.value)}
              className="mt-1 w-full rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
            >
              {categories.map((c) => (
                <option key={c.id} value={c.id}>
                  {c.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex items-center gap-2 text-sm text-slate-600">
            <input type="checkbox" checked={publish} onChange={(e) => setPublish(e.target.checked)} />
            入库后立即发布（可被检索与对话引用）
          </label>
          <button
            type="button"
            disabled={loading || !url.trim()}
            onClick={() => void onPreview()}
            className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
            {loading ? "采集中…" : "采集并预览"}
          </button>
        </div>
      ) : preview ? (
        <div className="space-y-4">
          <div className="rounded-xl border border-slate-100 bg-slate-50/80 px-4 py-3">
            <p className="text-sm font-medium text-slate-900">{preview.title}</p>
            {preview.page_title ? (
              <p className="mt-0.5 text-xs text-slate-500">原网页标题：{preview.page_title}</p>
            ) : null}
            {preview.summary ? (
              <p className="mt-2 text-xs leading-relaxed text-slate-600">{preview.summary}</p>
            ) : null}
            <p className="mt-2 text-xs text-slate-400">
              来源：<span className="break-all">{preview.url}</span> · {preview.content.length.toLocaleString()} 字
            </p>
          </div>
          <div className="max-h-[min(50vh,28rem)] overflow-y-auto rounded-xl border border-slate-200 bg-white p-4">
            <MarkdownPreview markdown={preview.content} />
          </div>
          <div className="flex flex-wrap gap-2">
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
              className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
            >
              {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
              {loading ? "入库中…" : "确认入库"}
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
