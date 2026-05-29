import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useLocation, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { ArrowLeft, Link2, Sparkles } from "lucide-react";

import { KnowledgeGapsPanel } from "@/components/KnowledgeGapsPanel";
import { UrlImportPanel } from "@/components/UrlImportPanel";
import { useUi } from "@/components/ui/UiProvider";
import { flattenCategoryTree, listCategoryTree } from "@/services/categories";
import { getAccessToken } from "@/services/auth";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";

type ProdTab = "url" | "distill";

/**
 * 知识生产工作台：URL 采集 + 缺口蒸馏（P1 扩展生产方式）。
 */
export function KnowledgeProductionPage() {
  const { kbId: routeKbId } = useParams<{ kbId?: string }>();
  const { pathname } = useLocation();
  const isStandalone = pathname === "/production";
  const [searchParams, setSearchParams] = useSearchParams();
  const nav = useNavigate();
  const { message } = useUi();
  const tabParam = searchParams.get("tab");
  const tab: ProdTab = tabParam === "distill" ? "distill" : "url";
  const kbFromQuery = searchParams.get("kb_id") ?? "";

  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [kbId, setKbId] = useState(routeKbId || kbFromQuery || "");
  const [categories, setCategories] = useState<{ id: string; label: string }[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [importTick, setImportTick] = useState(0);

  const kbName = useMemo(() => kbs.find((k) => k.id === kbId)?.name ?? "知识库", [kbs, kbId]);

  const loadKbs = useCallback(async () => {
    if (!getAccessToken()) {
      nav("/login", { replace: true });
      return;
    }
    const rows = await listKnowledgeBases();
    setKbs(rows);
    setKbId((cur) => cur || routeKbId || kbFromQuery || rows[0]?.id || "");
  }, [nav, routeKbId, kbFromQuery]);

  useEffect(() => {
    if (routeKbId && routeKbId !== kbId) {
      setKbId(routeKbId);
    }
  }, [routeKbId, kbId]);

  useEffect(() => {
    if (isStandalone && kbFromQuery && kbFromQuery !== kbId) {
      setKbId(kbFromQuery);
    }
  }, [isStandalone, kbFromQuery, kbId]);

  const loadCategories = useCallback(async () => {
    if (!kbId) return;
    try {
      const tree = await listCategoryTree(kbId);
      setCategories(flattenCategoryTree(tree));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载分类失败");
    }
  }, [kbId]);

  useEffect(() => {
    void loadKbs().catch((e) => setErr(e instanceof Error ? e.message : "加载失败"));
  }, [loadKbs]);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  useEffect(() => {
    if (!kbId) return;
    if (isStandalone) {
      const next = new URLSearchParams(searchParams);
      let changed = false;
      if (next.get("kb_id") !== kbId) {
        next.set("kb_id", kbId);
        changed = true;
      }
      if (next.get("tab") !== tab) {
        next.set("tab", tab);
        changed = true;
      }
      if (changed) setSearchParams(next, { replace: true });
    } else if (routeKbId && kbId !== routeKbId) {
      nav(`/knowledge-bases/${kbId}/production?tab=${tab}`, { replace: true });
    }
  }, [kbId, routeKbId, nav, tab, isStandalone, searchParams, setSearchParams]);

  const setTab = (next: ProdTab) => {
    setSearchParams({ tab: next }, { replace: true });
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-6 lg:p-8">
      <header className="mb-6">
        <Link
          to="/documents"
          className="mb-3 inline-flex items-center gap-1 text-xs font-medium text-slate-500 hover:text-primary"
        >
          <ArrowLeft className="h-3.5 w-3.5" />
          返回文档管理
        </Link>
        <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">知识生产</h1>
        <p className="mt-1 max-w-2xl text-xs text-slate-600 lg:text-sm">
          除 PDF 上传与手动录入外，可通过 URL 采集网页、或通过缺口蒸馏从对话日志补全知识。
        </p>
      </header>

      {err ? (
        <p className="mb-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p>
      ) : null}

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <label className="text-xs font-medium text-slate-600">
          目标知识库
          <select
            value={kbId}
            onChange={(e) => setKbId(e.target.value)}
            className="ml-0 mt-1 block min-w-[12rem] rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm sm:ml-2 sm:mt-0 sm:inline-block"
          >
            {kbs.map((k) => (
              <option key={k.id} value={k.id}>
                {k.name}
              </option>
            ))}
          </select>
        </label>
      </div>

      <div className="mb-4 flex gap-1 rounded-xl border border-slate-200 bg-white p-1 shadow-sm">
        <button
          type="button"
          onClick={() => setTab("url")}
          className={
            tab === "url"
              ? "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-primary-soft py-2.5 text-sm font-semibold text-primary"
              : "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm text-slate-600 hover:bg-slate-50"
          }
        >
          <Link2 className="h-4 w-4" />
          URL 采集
        </button>
        <button
          type="button"
          onClick={() => setTab("distill")}
          className={
            tab === "distill"
              ? "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg bg-violet-100 py-2.5 text-sm font-semibold text-violet-800"
              : "inline-flex flex-1 items-center justify-center gap-1.5 rounded-lg py-2.5 text-sm text-slate-600 hover:bg-slate-50"
          }
        >
          <Sparkles className="h-4 w-4" />
          缺口蒸馏
        </button>
      </div>

      {!kbId ? (
        <p className="text-sm text-slate-500">请先创建并选择知识库。</p>
      ) : tab === "url" ? (
        <UrlImportPanel
          key={`${kbId}-${importTick}`}
          kbId={kbId}
          categories={categories}
          onImported={() => {
            setImportTick((n) => n + 1);
            message.success("URL 内容已入库");
          }}
        />
      ) : (
        <KnowledgeGapsPanel kbId={kbId} variant="page" />
      )}

      {kbId ? (
        <p className="mt-6 text-center text-xs text-slate-400">
          当前库：{kbName} · 入库后可在
          <button
            type="button"
            onClick={() => nav("/documents")}
            className="mx-1 text-primary hover:underline"
          >
            文档管理 → 条目视图
          </button>
          审核与发布
        </p>
      ) : null}
    </div>
  );
}
