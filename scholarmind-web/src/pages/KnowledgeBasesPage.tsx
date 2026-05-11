import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { BookOpen, LayoutGrid, List, Plus, Search, Trash2 } from "lucide-react";

import { getAccessToken } from "@/services/auth";
import {
  createKnowledgeBase,
  deleteKnowledgeBase,
  listKnowledgeBases,
  type KnowledgeBaseDto,
} from "@/services/knowledgeBases";

function formatDate(iso: string): string {
  try {
    return new Date(iso).toLocaleDateString(undefined, {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
    });
  } catch {
    return iso;
  }
}

/**
 * 知识库管理：桌面栅格；移动端顶栏标题 + 搜索/筛选/视图切换 + 卡片（文献/大小/更新 + 菜单）。
 */
export function KnowledgeBasesPage() {
  const nav = useNavigate();
  const [view, setView] = useState<"grid" | "list">("grid");
  const [items, setItems] = useState<KnowledgeBaseDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [saving, setSaving] = useState(false);
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    if (!q) return items;
    return items.filter((k) => k.name.toLowerCase().includes(q));
  }, [items, query]);

  const load = useCallback(async () => {
    if (!getAccessToken()) {
      nav("/login", { replace: true });
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const rows = await listKnowledgeBases();
      setItems(rows);
    } catch (e) {
      const msg = e instanceof Error ? e.message : "加载失败";
      setError(msg);
      if (msg.includes("未登录") || msg.includes("401")) {
        nav("/login", { replace: true });
      }
    } finally {
      setLoading(false);
    }
  }, [nav]);

  useEffect(() => {
    void load();
  }, [load]);

  const onCreate = async () => {
    const name = newName.trim();
    if (!name) return;
    setSaving(true);
    setError(null);
    try {
      const kb = await createKnowledgeBase(name);
      setItems((prev) => [kb, ...prev]);
      setNewName("");
      setShowCreate(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "创建失败");
    } finally {
      setSaving(false);
    }
  };

  const onDelete = async (id: string, title: string) => {
    if (!window.confirm(`确定删除知识库「${title}」？`)) return;
    setError(null);
    try {
      await deleteKnowledgeBase(id);
      setItems((prev) => prev.filter((k) => k.id !== id));
    } catch (e) {
      setError(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-2 lg:p-8">
      <header className="mb-4 flex items-center justify-between gap-3 lg:mb-6 lg:hidden">
        <h1 className="text-lg font-semibold text-slate-900">知识库</h1>
        <button
          type="button"
          onClick={() => setShowCreate(true)}
          className="flex h-10 w-10 items-center justify-center rounded-full bg-primary text-white shadow-md hover:bg-primary-hover"
          aria-label="创建知识库"
        >
          <Plus className="h-5 w-5" />
        </button>
      </header>

      <header className="mb-6 hidden flex-col gap-4 lg:flex lg:flex-row lg:items-center lg:justify-between">
        <div>
          <h1 className="text-xl font-semibold text-slate-900">知识库</h1>
          <p className="text-sm text-slate-500">管理科研文献集合与访问范围</p>
        </div>
        <div className="flex flex-1 flex-col gap-3 sm:max-w-xl sm:flex-row sm:items-center">
          <div className="relative flex-1">
            <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none ring-primary focus:border-primary focus:ring-2"
              placeholder="搜索知识库…"
            />
          </div>
          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover"
          >
            <Plus className="h-4 w-4" />
            创建知识库
          </button>
        </div>
      </header>

      {/* 移动端：搜索 + 筛选 + 视图 */}
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-center lg:hidden">
        <div className="relative flex-1">
          <Search className="pointer-events-none absolute left-3 top-2.5 h-4 w-4 text-slate-400" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            className="w-full rounded-xl border border-slate-200 bg-white py-2.5 pl-9 pr-3 text-sm outline-none ring-primary focus:border-primary focus:ring-2"
            placeholder="搜索知识库…"
          />
        </div>
        <div className="flex gap-2">
          <select className="min-w-0 flex-1 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-800">
            <option>全部知识库</option>
            <option>仅私有</option>
            <option>仅共享</option>
          </select>
          <div className="flex rounded-xl border border-slate-200 bg-white p-0.5">
            <button
              type="button"
              onClick={() => setView("grid")}
              className={
                view === "grid"
                  ? "rounded-lg bg-primary-soft p-2 text-primary"
                  : "rounded-lg p-2 text-slate-400 hover:text-slate-700"
              }
              aria-label="网格视图"
            >
              <LayoutGrid className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              className={
                view === "list"
                  ? "rounded-lg bg-primary-soft p-2 text-primary"
                  : "rounded-lg p-2 text-slate-400 hover:text-slate-700"
              }
              aria-label="列表视图"
            >
              <List className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {showCreate ? (
        <div className="mb-4 rounded-xl border border-slate-200 bg-white p-4 shadow-sm lg:mb-6">
          <p className="mb-2 text-sm font-medium text-slate-800">新建知识库</p>
          <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
            <input
              value={newName}
              onChange={(e) => setNewName(e.target.value)}
              maxLength={50}
              placeholder="名称（最多 50 字）"
              className="flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm outline-none ring-primary focus:border-primary focus:ring-2"
            />
            <div className="flex gap-2">
              <button
                type="button"
                disabled={saving}
                onClick={() => void onCreate()}
                className="rounded-lg bg-primary px-4 py-2 text-sm font-semibold text-white hover:bg-primary-hover disabled:opacity-60"
              >
                {saving ? "保存中…" : "保存"}
              </button>
              <button
                type="button"
                onClick={() => {
                  setShowCreate(false);
                  setNewName("");
                }}
                className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
              >
                取消
              </button>
            </div>
          </div>
        </div>
      ) : null}

      {error ? (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      {loading ? (
        <p className="text-sm text-slate-500">加载中…</p>
      ) : (
        <div
          className={
            view === "list"
              ? "flex flex-col gap-3 lg:grid lg:grid-cols-2 xl:grid-cols-3 lg:gap-4"
              : "grid gap-3 sm:grid-cols-2 xl:grid-cols-3 lg:gap-4"
          }
        >
          {filtered.map((kb) => (
            <article
              key={kb.id}
              className="flex flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-card transition hover:border-primary/40 lg:rounded-xl lg:p-5"
            >
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary">
                  <BookOpen className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <h2 className="text-sm font-semibold leading-snug text-slate-900">{kb.name}</h2>
                    <div className="relative shrink-0">
                      <button
                        type="button"
                        className="rounded p-1 text-slate-400 hover:bg-slate-100 hover:text-slate-700"
                        title="删除"
                        aria-label="删除知识库"
                        onClick={() => void onDelete(kb.id, kb.name)}
                      >
                        <Trash2 className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                  <span className="mt-1 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                    私有
                  </span>
                  <p className="mt-1 text-[11px] text-slate-500">文献数 · {kb.doc_count}</p>
                </div>
              </div>
              <dl className="mt-3 grid grid-cols-3 gap-2 border-t border-slate-100 pt-3 text-[11px] text-slate-600 lg:grid-cols-2 lg:text-xs">
                <div>
                  <dt className="text-slate-400">文献</dt>
                  <dd className="font-semibold text-slate-900">{kb.doc_count.toLocaleString()}</dd>
                </div>
                <div>
                  <dt className="text-slate-400">存储</dt>
                  <dd className="font-semibold text-slate-900">—</dd>
                </div>
                <div className="lg:col-span-2">
                  <dt className="text-slate-400">更新</dt>
                  <dd className="font-semibold text-slate-900">{formatDate(kb.updated_at)}</dd>
                </div>
              </dl>
            </article>
          ))}

          <button
            type="button"
            onClick={() => setShowCreate(true)}
            className="flex min-h-[140px] flex-col items-center justify-center rounded-2xl border-2 border-dashed border-slate-200 bg-white text-sm font-medium text-slate-500 transition hover:border-primary hover:text-primary lg:min-h-[180px] lg:rounded-xl"
          >
            <Plus className="mb-2 h-8 w-8" />
            新建知识库
          </button>
        </div>
      )}
    </div>
  );
}
