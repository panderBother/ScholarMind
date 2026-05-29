import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, ExternalLink, FolderTree, Link2, Plus, Sparkles, Trash2 } from "lucide-react";

import { MarkdownPreview } from "@/components/MarkdownPreview";
import { UrlImportModal } from "@/components/UrlImportModal";
import { KnowledgeGapsPanel } from "@/components/KnowledgeGapsPanel";
import { ActionIcons } from "@/components/ui/ActionIcons";
import { useUi } from "@/components/ui/UiProvider";
import {
  createCategory,
  deleteCategory,
  flattenCategoryTree,
  listCategoryTree,
  type CategoryTreeNode,
} from "@/services/categories";
import { getDocument } from "@/services/documents";
import {
  archiveKnowledgeItem,
  createKnowledgeItem,
  deleteKnowledgeItem,
  listKnowledgeItems,
  publishKnowledgeItem,
  updateKnowledgeItem,
  type KnowledgeItemDto,
} from "@/services/knowledgeItems";
import { searchKnowledgeBase, type SearchHitDto } from "@/services/search";
import {
  buildKnowledgeItemDeleteConfirm,
  isKnowledgeItemContentReadonly,
  SOURCE_LABEL,
} from "@/utils/knowledgeItemUtils";

const STATUS_TABS = ["全部", "已发布", "草稿", "已下架"] as const;

const STATUS_MAP: Record<string, string | undefined> = {
  全部: undefined,
  已发布: "published",
  草稿: "draft",
  已下架: "archived",
};

type Props = {
  kbId: string;
  documentId?: string;
  documentName?: string;
  onClearDocumentFilter?: () => void;
};

export function KnowledgeItemsPanel({ kbId, documentId, documentName, onClearDocumentFilter }: Props) {
  const nav = useNavigate();
  const { confirm } = useUi();
  const [items, setItems] = useState<KnowledgeItemDto[]>([]);
  const [categories, setCategories] = useState<CategoryTreeNode[]>([]);
  const [statusTab, setStatusTab] = useState<string>("全部");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [keyword, setKeyword] = useState("");
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showEditor, setShowEditor] = useState(false);
  const [showCategories, setShowCategories] = useState(false);
  const [showUrl, setShowUrl] = useState(false);
  const [showGaps, setShowGaps] = useState(false);
  const [editing, setEditing] = useState<KnowledgeItemDto | null>(null);
  const [searchHits, setSearchHits] = useState<SearchHitDto[]>([]);

  const isHybridSearch = Boolean(keyword.trim());

  const openItemDetail = (item: KnowledgeItemDto) => {
    nav(`/documents/items/${kbId}/${item.id}`);
  };

  const categoryOptions = useMemo(() => flattenCategoryTree(categories), [categories]);

  const loadCategories = useCallback(async () => {
    if (!kbId) return;
    const tree = await listCategoryTree(kbId);
    setCategories(tree);
  }, [kbId]);

  const loadItems = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    setErr(null);
    const kw = keyword.trim();
    try {
      if (kw) {
        const res = await searchKnowledgeBase(kbId, {
          q: kw,
          limit: 50,
          categoryId: categoryFilter || undefined,
        });
        setSearchHits(res.items);
        setItems([]);
      } else {
        setSearchHits([]);
        const rows = await listKnowledgeItems(kbId, {
          lifecycle_status: STATUS_MAP[statusTab],
          category_id: categoryFilter || undefined,
          document_id: documentId || undefined,
        });
        setItems(rows);
      }
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载条目失败");
    } finally {
      setLoading(false);
    }
  }, [kbId, statusTab, categoryFilter, keyword, documentId]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    void loadItems();
  }, [loadItems]);

  const onPublish = async (item: KnowledgeItemDto) => {
    try {
      await publishKnowledgeItem(kbId, item.id);
      await loadItems();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "发布失败");
    }
  };

  const onArchive = async (item: KnowledgeItemDto) => {
    try {
      await archiveKnowledgeItem(kbId, item.id);
      await loadItems();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "下架失败");
    }
  };

  const onDelete = async (item: KnowledgeItemDto) => {
    let documentLabel: string | null = null;
    if (item.document_id) {
      try {
        const doc = await getDocument(kbId, item.document_id);
        documentLabel = doc.title || doc.filename;
      } catch {
        documentLabel = null;
      }
    }
    const { title, message } = buildKnowledgeItemDeleteConfirm(item, documentLabel);
    const ok = await confirm({
      title,
      message,
      confirmText: "删除",
      type: "danger",
    });
    if (!ok) return;
    try {
      await deleteKnowledgeItem(kbId, item.id);
      await loadItems();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div className="space-y-4">
      {err ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {err}
        </p>
      ) : null}

      {documentId ? (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/20 bg-primary-soft px-3 py-2 text-sm">
          <span className="text-slate-700">
            正在编辑文档「<strong>{documentName ?? "未知"}</strong>」的识别内容（一文档一条目）
          </span>
          {onClearDocumentFilter ? (
            <button
              type="button"
              onClick={onClearDocumentFilter}
              className="font-semibold text-primary hover:underline"
            >
              显示全部条目
            </button>
          ) : null}
        </div>
      ) : null}

      <div className="flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => {
            setEditing(null);
            setShowEditor(true);
          }}
          disabled={!kbId || categoryOptions.length === 0}
          className="inline-flex items-center gap-1.5 rounded-lg bg-primary px-3 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-50"
        >
          <Plus className="h-4 w-4" />
          新建条目
        </button>
        <button
          type="button"
          onClick={() => setShowCategories(true)}
          disabled={!kbId}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <FolderTree className="h-4 w-4" />
          分类管理
        </button>
        <button
          type="button"
          onClick={() => setShowUrl(true)}
          disabled={!kbId || categoryOptions.length === 0}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          <Link2 className="h-4 w-4" />
          URL 采集
        </button>
        <button
          type="button"
          onClick={() => setShowGaps(true)}
          disabled={!kbId}
          className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm text-violet-800 hover:bg-violet-100"
        >
          <Sparkles className="h-4 w-4" />
          知识缺口
        </button>
        <button
          type="button"
          onClick={() => nav(`/production?kb_id=${encodeURIComponent(kbId)}`)}
          disabled={!kbId}
          className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 px-3 py-2 text-xs text-slate-600 hover:bg-slate-50"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          知识生产工作台
        </button>
      </div>

      <div className="flex flex-wrap gap-2">
        <input
          type="search"
          placeholder="混合检索（语义 + 关键词）…"
          value={keyword}
          onChange={(e) => setKeyword(e.target.value)}
          className="min-w-[12rem] flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm"
        />
        <select
          value={categoryFilter}
          onChange={(e) => setCategoryFilter(e.target.value)}
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
        >
          <option value="">全部分类</option>
          {categoryOptions.map((c) => (
            <option key={c.id} value={c.id}>
              {c.label}
            </option>
          ))}
        </select>
      </div>

      <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-card lg:rounded-xl">
        <div className="flex gap-1 overflow-x-auto border-b border-slate-100 px-2 py-2 lg:px-4">
          {isHybridSearch ? (
            <p className="px-2 py-1.5 text-xs text-slate-500">
              混合检索模式：仅显示已发布条目（状态筛选已暂停）
            </p>
          ) : (
            STATUS_TABS.map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setStatusTab(t)}
                className={
                  t === statusTab
                    ? "shrink-0 rounded-full bg-primary-soft px-3 py-1.5 text-xs font-semibold text-primary"
                    : "shrink-0 rounded-full px-3 py-1.5 text-xs text-slate-500 hover:bg-slate-50"
                }
              >
                {t}
              </button>
            ))
          )}
        </div>

        {loading ? (
          <p className="p-4 text-sm text-slate-500">加载中…</p>
        ) : isHybridSearch && searchHits.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500">未找到匹配的已发布条目。</p>
        ) : !isHybridSearch && items.length === 0 ? (
          <p className="p-6 text-center text-sm text-slate-500">
            {documentId
              ? "该文档尚无对应条目，或尚未解析完成。"
              : "暂无条目。文档入库后会自动生成一条「已发布」条目；也可手动新建。"}
          </p>
        ) : isHybridSearch ? (
          <ul className="divide-y divide-slate-100">
            {searchHits.map((hit) => (
              <li
                key={`${hit.item_id}-${hit.page ?? 0}`}
                className="cursor-pointer p-4 hover:bg-slate-50/60"
                onClick={() => nav(`/documents/items/${kbId}/${hit.item_id}`)}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <BookOpen className="h-4 w-4 shrink-0 text-primary" />
                      <h3 className="font-medium text-slate-900">{hit.title}</h3>
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {SOURCE_LABEL[hit.source_type] ?? hit.source_type}
                      </span>
                      <span className="rounded-full bg-primary/10 px-2 py-0.5 text-[10px] font-medium text-primary">
                        相关度 {hit.score.toFixed(3)}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">{hit.snippet}</p>
                  </div>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <ul className="divide-y divide-slate-100">
            {items.map((item) => (
              <li
                key={item.id}
                className="cursor-pointer p-4 hover:bg-slate-50/60"
                onClick={() => openItemDetail(item)}
              >
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <BookOpen className="h-4 w-4 shrink-0 text-primary" />
                      <h3 className="font-medium text-slate-900">{item.title}</h3>
                      <StatusPill status={item.lifecycle_status} />
                      <span className="rounded-full bg-slate-100 px-2 py-0.5 text-xs text-slate-600">
                        {SOURCE_LABEL[item.source_type] ?? item.source_type}
                      </span>
                    </div>
                    <p className="mt-1 line-clamp-2 text-xs text-slate-500">{item.content.slice(0, 200)}</p>
                    {item.source ? (
                      <p className="mt-1 text-xs text-slate-400">来源：{item.source}</p>
                    ) : null}
                  </div>
                  <ActionIcons
                    onPreview={() => openItemDetail(item)}
                    onEdit={
                      !isKnowledgeItemContentReadonly(item)
                        ? () => openItemDetail(item)
                        : undefined
                    }
                    onPublish={item.lifecycle_status === "draft" ? () => void onPublish(item) : undefined}
                    onArchive={
                      item.lifecycle_status === "published" && item.source_type === "manual"
                        ? () => void onArchive(item)
                        : undefined
                    }
                    onDelete={() => void onDelete(item)}
                  />
                </div>
              </li>
            ))}
          </ul>
        )}

        <div className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
          共 {isHybridSearch ? searchHits.length : items.length} 条
          {isHybridSearch ? "（混合检索）" : null}
        </div>
      </section>

      {showEditor ? (
        <ItemEditorModal
          kbId={kbId}
          categories={categoryOptions}
          item={editing}
          onClose={() => {
            setShowEditor(false);
            setEditing(null);
          }}
          onSaved={() => {
            setShowEditor(false);
            setEditing(null);
            void loadItems();
          }}
        />
      ) : null}

      {showCategories ? (
        <CategoryDrawer
          kbId={kbId}
          tree={categories}
          onClose={() => setShowCategories(false)}
          onChanged={() => {
            void loadCategories();
            void loadItems();
          }}
        />
      ) : null}

      {showUrl ? (
        <UrlImportModal
          kbId={kbId}
          categories={categoryOptions}
          onClose={() => setShowUrl(false)}
          onImported={() => {
            setShowUrl(false);
            void loadItems();
          }}
        />
      ) : null}

      {showGaps ? (
        <KnowledgeGapsPanel
          kbId={kbId}
          variant="modal"
          onClose={() => setShowGaps(false)}
          onChanged={() => void loadItems()}
        />
      ) : null}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    published: "bg-emerald-50 text-emerald-700",
    draft: "bg-amber-50 text-amber-700",
    archived: "bg-red-50 text-red-700",
    disabled: "bg-red-50 text-red-700",
  };
  const label: Record<string, string> = {
    published: "已发布",
    draft: "草稿",
    archived: "已下架",
    disabled: "已下架",
  };
  return (
    <span className={`rounded-full px-2 py-0.5 text-xs font-medium ${map[status] ?? map.draft}`}>
      {label[status] ?? status}
    </span>
  );
}

function ItemEditorModal({
  kbId,
  categories,
  item,
  onClose,
  onSaved,
}: {
  kbId: string;
  categories: { id: string; label: string }[];
  item: KnowledgeItemDto | null;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [title, setTitle] = useState(item?.title ?? "");
  const [content, setContent] = useState(item?.content ?? "");
  const [categoryId, setCategoryId] = useState(item?.category_id ?? categories[0]?.id ?? "");
  const [summary, setSummary] = useState(item?.summary ?? "");
  const [publishNow, setPublishNow] = useState(false);
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const onSubmit = async () => {
    if (!title.trim() || !content.trim() || !categoryId) {
      setErr("请填写标题、正文并选择分类");
      return;
    }
    setSaving(true);
    setErr(null);
    try {
      if (item) {
        await updateKnowledgeItem(kbId, item.id, {
          title: title.trim(),
          content: content.trim(),
          category_id: categoryId,
          summary: summary.trim() || undefined,
        });
        if (publishNow && item.lifecycle_status === "draft") {
          await publishKnowledgeItem(kbId, item.id);
        }
      } else {
        await createKnowledgeItem(kbId, {
          title: title.trim(),
          content: content.trim(),
          category_id: categoryId,
          summary: summary.trim() || undefined,
          publish: publishNow,
        });
      }
      onSaved();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "保存失败");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 lg:items-center">
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
        <div className="flex items-center justify-between border-b border-slate-100 px-4 py-3">
          <h2 className="font-semibold text-slate-900">
            {item ? (item.source_type === "document" ? "编辑文档识别内容" : "编辑条目") : "新建知识条目"}
          </h2>
          <button type="button" onClick={onClose} className="text-sm text-slate-500 hover:text-slate-800">
            关闭
          </button>
        </div>
        {err ? <p className="bg-red-50 px-4 py-2 text-sm text-red-700">{err}</p> : null}
        <div className="grid flex-1 gap-4 overflow-y-auto p-4 lg:grid-cols-2">
          <div className="space-y-3">
            <input
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="标题"
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
            <input
              value={summary}
              onChange={(e) => setSummary(e.target.value)}
              placeholder="摘要（可选）"
              className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
            />
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Markdown 正文"
              rows={14}
              className="w-full rounded-lg border border-slate-200 px-3 py-2 font-mono text-sm"
            />
            {!item || item.lifecycle_status === "draft" ? (
              <label className="flex items-center gap-2 text-sm text-slate-600">
                <input type="checkbox" checked={publishNow} onChange={(e) => setPublishNow(e.target.checked)} />
                保存后立即发布（可检索）
              </label>
            ) : null}
          </div>
          <div className="rounded-lg border border-slate-100 bg-slate-50/50 p-3">
            <p className="mb-2 text-xs font-medium text-slate-500">预览</p>
            <MarkdownPreview markdown={content || "（空）"} />
          </div>
        </div>
        <div className="flex justify-end gap-2 border-t border-slate-100 px-4 py-3">
          <button type="button" onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-600">
            取消
          </button>
          <button
            type="button"
            disabled={saving}
            onClick={() => void onSubmit()}
            className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
          >
            {saving ? "保存中…" : "保存"}
          </button>
        </div>
      </div>
    </div>
  );
}

function CategoryDrawer({
  kbId,
  tree,
  onClose,
  onChanged,
}: {
  kbId: string;
  tree: CategoryTreeNode[];
  onClose: () => void;
  onChanged: () => void;
}) {
  const { confirm } = useUi();
  const [name, setName] = useState("");
  const [parentId, setParentId] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const flat = useMemo(() => flattenCategoryTree(tree), [tree]);

  const onAdd = async () => {
    if (!name.trim()) return;
    setErr(null);
    try {
      await createCategory(kbId, { name: name.trim(), parent_id: parentId || null });
      setName("");
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "添加失败");
    }
  };

  const onRemove = async (id: string, label: string) => {
    const ok = await confirm({
      title: "删除分类",
      message: `删除分类「${label.trim()}」？`,
      confirmText: "删除",
      type: "danger",
    });
    if (!ok) return;
    try {
      await deleteCategory(kbId, id);
      onChanged();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex justify-end bg-black/40">
      <div className="flex h-full w-full max-w-md flex-col bg-white shadow-xl">
        <div className="flex items-center justify-between border-b px-4 py-3">
          <h2 className="font-semibold">分类管理</h2>
          <button type="button" onClick={onClose} className="text-sm text-slate-500">
            关闭
          </button>
        </div>
        {err ? <p className="bg-red-50 px-4 py-2 text-sm text-red-700">{err}</p> : null}
        <div className="space-y-2 border-b p-4">
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="新分类名称"
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          />
          <select
            value={parentId}
            onChange={(e) => setParentId(e.target.value)}
            className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
          >
            <option value="">顶级分类</option>
            {flat.map((c) => (
              <option key={c.id} value={c.id}>
                {c.label}
              </option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => void onAdd()}
            className="w-full rounded-lg bg-primary py-2 text-sm font-semibold text-white"
          >
            添加分类
          </button>
        </div>
        <ul className="flex-1 overflow-y-auto divide-y divide-slate-100 p-2">
          {flat.map((c) => (
            <li key={c.id} className="flex items-center justify-between px-2 py-2 text-sm">
              <span>{c.label}</span>
              {c.label.trim() !== "未分类" && (
                <button
                  type="button"
                  onClick={() => void onRemove(c.id, c.label)}
                  className="rounded p-1 text-red-500 hover:bg-red-50"
                  aria-label="删除"
                >
                  <Trash2 className="h-4 w-4" />
                </button>
              )}
            </li>
          ))}
        </ul>
      </div>
    </div>
  );
}
