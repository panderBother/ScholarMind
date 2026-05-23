import { useCallback, useEffect, useMemo, useState } from "react";
import clsx from "clsx";
import { ArrowLeft, BookOpen, ExternalLink, Link2, Loader2, Trash2 } from "lucide-react";
import { useNavigate, useParams } from "react-router-dom";

import { MarkdownPreview } from "@/components/MarkdownPreview";
import { useUi } from "@/components/ui/UiProvider";
import { flattenCategoryTree, listCategoryTree } from "@/services/categories";
import {
  archiveKnowledgeItem,
  deleteKnowledgeItem,
  getKnowledgeItem,
  publishKnowledgeItem,
  updateKnowledgeItem,
  type KnowledgeItemDto,
} from "@/services/knowledgeItems";
import {
  canArchiveKnowledgeItem,
  canDeleteKnowledgeItem,
  isKnowledgeItemContentReadonly,
  SOURCE_LABEL,
} from "@/utils/knowledgeItemUtils";

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    published: "bg-emerald-50 text-emerald-700",
    draft: "bg-amber-50 text-amber-700",
    archived: "bg-slate-100 text-slate-600",
    disabled: "bg-red-50 text-red-700",
  };
  const label: Record<string, string> = {
    published: "已发布",
    draft: "草稿",
    archived: "已归档",
    disabled: "已下架",
  };
  return (
    <span className={clsx("rounded-full px-2 py-0.5 text-xs font-medium", map[status] ?? map.draft)}>
      {label[status] ?? status}
    </span>
  );
}

export function KnowledgeItemDetailPage() {
  const nav = useNavigate();
  const { kbId, itemId } = useParams<{ kbId: string; itemId: string }>();
  const { confirm, message } = useUi();

  const [item, setItem] = useState<KnowledgeItemDto | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [summary, setSummary] = useState("");
  const [categoryId, setCategoryId] = useState("");
  const [categoryOptions, setCategoryOptions] = useState<{ id: string; label: string }[]>([]);

  const readonly = item ? isKnowledgeItemContentReadonly(item) : false;
  const isDraft = item?.lifecycle_status === "draft";

  const load = useCallback(async () => {
    if (!kbId || !itemId) return;
    setLoading(true);
    setErr(null);
    try {
      const [row, tree] = await Promise.all([getKnowledgeItem(kbId, itemId), listCategoryTree(kbId)]);
      setItem(row);
      setTitle(row.title);
      setContent(row.content);
      setSummary(row.summary ?? "");
      setCategoryId(row.category_id ?? "");
      setCategoryOptions(flattenCategoryTree(tree));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbId, itemId]);

  useEffect(() => {
    void load();
  }, [load]);

  const dirty = useMemo(() => {
    if (!item || readonly) return false;
    return (
      title.trim() !== item.title ||
      content.trim() !== item.content ||
      (summary.trim() || "") !== (item.summary ?? "") ||
      categoryId !== (item.category_id ?? "")
    );
  }, [item, readonly, title, content, summary, categoryId]);

  const validate = (): string | null => {
    if (!title.trim()) return "请填写标题";
    if (!content.trim()) return "请填写正文";
    if (!categoryId) return "请选择分类";
    return null;
  };

  const persist = async (publish: boolean) => {
    if (!kbId || !itemId || !item || readonly) return;
    const validationErr = validate();
    if (validationErr) {
      setErr(validationErr);
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      const updated = await updateKnowledgeItem(kbId, itemId, {
        title: title.trim(),
        content: content.trim(),
        category_id: categoryId,
        summary: summary.trim() || undefined,
      });
      let next = updated;
      if (publish && updated.lifecycle_status === "draft") {
        next = await publishKnowledgeItem(kbId, itemId);
      }
      setItem(next);
      setTitle(next.title);
      setContent(next.content);
      setSummary(next.summary ?? "");
      setCategoryId(next.category_id ?? "");
      message.success(publish ? "已保存并发布" : isDraft ? "已保存为草稿" : "已保存更改");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  const onSaveDraft = () => void persist(false);

  const onSaveAndPublish = async () => {
    if (!item || readonly) return;
    if (isDraft) {
      const ok = await confirm({
        title: "发布条目",
        message: "保存后将立即发布，条目可被对话检索引用。确定继续？",
        confirmText: "保存并发布",
      });
      if (!ok) return;
    }
    await persist(true);
  };

  const onArchive = async () => {
    if (!kbId || !item) return;
    const ok = await confirm({
      title: "归档条目",
      message: `归档后「${item.title}」将不再参与检索。`,
      confirmText: "归档",
    });
    if (!ok) return;
    try {
      const next = await archiveKnowledgeItem(kbId, item.id);
      setItem(next);
      message.success("已归档");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "归档失败");
    }
  };

  const onDelete = async () => {
    if (!kbId || !item) return;
    if (item.source_type === "document") {
      setErr("文献解析条目请通过删除文献移除");
      return;
    }
    const ok = await confirm({
      title: "删除条目",
      message: `确定删除「${item.title}」？此操作不可恢复。`,
      confirmText: "删除",
      type: "danger",
    });
    if (!ok) return;
    setDeleting(true);
    try {
      await deleteKnowledgeItem(kbId, item.id);
      message.success("条目已删除");
      nav("/documents", { state: { kbId, viewTab: "条目视图" } });
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    } finally {
      setDeleting(false);
    }
  };

  const goBack = () => {
    nav("/documents", { state: { kbId, viewTab: "条目视图" } });
  };

  if (loading) {
    return (
      <div className="flex min-h-0 flex-1 items-center justify-center p-8 text-slate-500">
        <Loader2 className="mr-2 h-5 w-5 animate-spin" />
        加载中…
      </div>
    );
  }

  if (!item) {
    return (
      <div className="p-8">
        <p className="text-sm text-red-600">{err ?? "条目不存在"}</p>
        <button type="button" onClick={goBack} className="mt-4 text-sm text-primary hover:underline">
          返回文献管理
        </button>
      </div>
    );
  }

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 lg:p-8">
      <div className="mx-auto max-w-5xl space-y-4">
        <button
          type="button"
          onClick={goBack}
          className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-800"
        >
          <ArrowLeft className="h-4 w-4" />
          返回条目列表
        </button>

        {err ? (
          <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
            {err}
          </p>
        ) : null}

        <header className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0 flex-1 space-y-2">
              <div className="flex flex-wrap items-center gap-2">
                {readonly ? (
                  <Link2 className="h-5 w-5 shrink-0 text-violet-500" />
                ) : (
                  <BookOpen className="h-5 w-5 shrink-0 text-primary" />
                )}
                <StatusPill status={item.lifecycle_status} />
                <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                  {SOURCE_LABEL[item.source_type] ?? item.source_type}
                </span>
                {readonly ? (
                  <span className="rounded-full bg-amber-50 px-2 py-0.5 text-xs text-amber-800">
                    只读 · URL 采集不可修改
                  </span>
                ) : null}
              </div>
              {readonly ? (
                <h1 className="text-xl font-semibold text-slate-900">{item.title}</h1>
              ) : (
                <input
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  className="w-full rounded-lg border border-slate-200 px-3 py-2 text-lg font-semibold text-slate-900"
                  placeholder="标题"
                />
              )}
              {item.source ? (
                <p className="text-xs text-slate-500">
                  来源：
                  {item.source_type === "url" ? (
                    <a
                      href={item.source}
                      target="_blank"
                      rel="noreferrer"
                      className="ml-1 inline-flex items-center gap-0.5 text-primary hover:underline"
                    >
                      {item.source}
                      <ExternalLink className="h-3 w-3" />
                    </a>
                  ) : (
                    <span className="ml-1">{item.source}</span>
                  )}
                </p>
              ) : null}
              {item.page != null ? (
                <p className="text-xs text-slate-400">文献页码：第 {item.page + 1} 页</p>
              ) : null}
            </div>
            {readonly && item.source ? (
              <a
                href={item.source}
                target="_blank"
                rel="noreferrer"
                className="inline-flex shrink-0 items-center gap-1 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" />
                打开原网页
              </a>
            ) : null}
          </div>
        </header>

        {readonly ? (
          <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:p-6">
            {item.summary ? (
              <p className="mb-4 rounded-lg bg-slate-50 px-3 py-2 text-sm text-slate-600">{item.summary}</p>
            ) : null}
            <p className="mb-2 text-xs font-medium text-slate-500">完整正文</p>
            <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
              <MarkdownPreview markdown={item.content || "（空）"} />
            </div>
            {item.content ? (
              <p className="mt-2 text-xs text-slate-400">共 {item.content.length.toLocaleString()} 字</p>
            ) : null}
            <p className="mt-4 text-xs text-slate-500">
              URL 采集内容自源站导入，为保证准确性不可编辑。如需调整，请重新采集或手动新建条目。
            </p>
          </section>
        ) : (
          <div className="grid gap-4 lg:grid-cols-2">
            <section className="space-y-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:p-6">
              <label className="block text-xs font-medium text-slate-500">分类</label>
              <select
                value={categoryId}
                onChange={(e) => setCategoryId(e.target.value)}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              >
                {categoryOptions.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
              <label className="block text-xs font-medium text-slate-500">摘要（可选）</label>
              <input
                value={summary}
                onChange={(e) => setSummary(e.target.value)}
                placeholder="简短摘要"
                className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
              />
              <label className="block text-xs font-medium text-slate-500">正文（Markdown）</label>
              <textarea
                value={content}
                onChange={(e) => setContent(e.target.value)}
                rows={18}
                className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm leading-relaxed"
                placeholder="Markdown 正文"
              />
              {content ? (
                <p className="text-xs text-slate-400">共 {content.length.toLocaleString()} 字</p>
              ) : null}
            </section>
            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:p-6">
              <p className="mb-2 text-xs font-medium text-slate-500">预览</p>
              <div className="min-h-[12rem] rounded-xl border border-slate-100 bg-slate-50/50 p-4">
                <MarkdownPreview markdown={content || "（空）"} />
              </div>
            </section>
          </div>
        )}

        {!readonly ? (
          <div className="sticky bottom-0 z-10 -mx-4 flex flex-wrap gap-2 border-t border-slate-200 bg-white/95 px-4 py-3 backdrop-blur lg:static lg:mx-0 lg:rounded-2xl lg:border lg:px-6 lg:shadow-card">
            <button
              type="button"
              disabled={saving || !dirty}
              onClick={onSaveDraft}
              className="flex-1 rounded-xl border border-slate-200 py-2.5 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-50 lg:flex-none lg:px-6"
            >
              {saving ? "保存中…" : isDraft ? "保存草稿" : "保存更改"}
            </button>
            {isDraft ? (
              <button
                type="button"
                disabled={saving}
                onClick={() => void onSaveAndPublish()}
                className="flex-1 rounded-xl bg-primary py-2.5 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50 lg:flex-none lg:px-6"
              >
                保存并发布
              </button>
            ) : null}
            {canArchiveKnowledgeItem(item) ? (
              <button
                type="button"
                onClick={() => void onArchive()}
                className="rounded-xl border border-amber-200 px-4 py-2.5 text-sm text-amber-800 hover:bg-amber-50"
              >
                归档
              </button>
            ) : null}
            {canDeleteKnowledgeItem(item) ? (
              <button
                type="button"
                disabled={deleting}
                onClick={() => void onDelete()}
                className="inline-flex items-center gap-1 rounded-xl border border-red-200 px-4 py-2.5 text-sm text-red-600 hover:bg-red-50 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
                删除
              </button>
            ) : null}
          </div>
        ) : null}
      </div>
    </div>
  );
}
