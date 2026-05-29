import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Loader2, Search } from "lucide-react";

import { getAccessToken } from "@/services/auth";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";
import { searchKnowledgeBase, type SearchHitDto } from "@/services/search";

/**
 * 全局知识检索：选择知识库后调用 hybrid_search API。
 */
export function SearchPage() {
  const nav = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [kbId, setKbId] = useState(searchParams.get("kbId") ?? "");
  const [query, setQuery] = useState(searchParams.get("q") ?? "");
  const [debouncedQ, setDebouncedQ] = useState(query.trim());
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hits, setHits] = useState<SearchHitDto[]>([]);
  const [total, setTotal] = useState(0);

  const kbName = useMemo(() => kbs.find((k) => k.id === kbId)?.name ?? "知识库", [kbs, kbId]);

  useEffect(() => {
    const t = window.setTimeout(() => setDebouncedQ(query.trim()), 300);
    return () => window.clearTimeout(t);
  }, [query]);

  useEffect(() => {
    const sp = new URLSearchParams();
    if (kbId) sp.set("kbId", kbId);
    if (debouncedQ) sp.set("q", debouncedQ);
    setSearchParams(sp, { replace: true });
  }, [kbId, debouncedQ, setSearchParams]);

  const loadKbs = useCallback(async () => {
    if (!getAccessToken()) {
      nav("/login", { replace: true });
      return;
    }
    const rows = await listKnowledgeBases();
    setKbs(rows);
    setKbId((cur) => cur || searchParams.get("kbId") || rows[0]?.id || "");
  }, [nav, searchParams]);

  useEffect(() => {
    void loadKbs();
  }, [loadKbs]);

  useEffect(() => {
    if (!kbId || !debouncedQ) {
      setHits([]);
      setTotal(0);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    void (async () => {
      try {
        const res = await searchKnowledgeBase(kbId, { q: debouncedQ, limit: 30 });
        if (cancelled) return;
        setHits(res.items);
        setTotal(res.total);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "检索失败");
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [kbId, debouncedQ]);

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-6 lg:p-8">
      <div className="mx-auto max-w-4xl space-y-4">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">知识检索</h1>
          <p className="mt-0.5 text-xs text-slate-500 lg:text-sm">
            混合检索（BM25 + 向量 + RRF + Rerank）· 仅已发布条目
          </p>
        </div>

        <div className="flex flex-col gap-3 sm:flex-row">
          <label className="flex flex-col gap-1 sm:w-56">
            <span className="text-[11px] font-medium text-slate-500">知识库</span>
            <select
              value={kbId}
              onChange={(e) => setKbId(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800"
            >
              {kbs.map((kb) => (
                <option key={kb.id} value={kb.id}>
                  {kb.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex min-w-0 flex-1 flex-col gap-1">
            <span className="text-[11px] font-medium text-slate-500">搜索</span>
            <div className="relative">
              <Search className="pointer-events-none absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
              <input
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder={`在「${kbName}」中检索…`}
                className="w-full rounded-lg border border-slate-200 bg-white py-2 pl-9 pr-3 text-sm outline-none focus:border-primary"
              />
            </div>
          </label>
        </div>

        {error ? (
          <p className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{error}</p>
        ) : null}

        {!debouncedQ ? (
          <p className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500 shadow-card">
            输入关键词开始检索
          </p>
        ) : loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> 检索中…
          </div>
        ) : (
          <>
            <p className="text-xs text-slate-500">共 {total} 条结果</p>
            <ul className="space-y-2">
              {hits.map((hit) => (
                <li key={hit.item_id}>
                  <button
                    type="button"
                    onClick={() => nav(`/documents/items/${kbId}/${hit.item_id}`)}
                    className="w-full rounded-xl border border-slate-200 bg-white p-4 text-left shadow-card transition hover:border-primary/30 hover:shadow-md"
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <h3 className="text-sm font-semibold text-slate-900">{hit.title}</h3>
                      <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                        {hit.source_type}
                      </span>
                      {hit.page != null ? (
                        <span className="rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-medium text-primary">
                          第 {hit.page + 1} 页
                        </span>
                      ) : null}
                      <span className="ml-auto text-[10px] tabular-nums text-slate-400">
                        相关度 {hit.score.toFixed(2)}
                      </span>
                    </div>
                    <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-slate-600">{hit.snippet}</p>
                    {hit.tags.length ? (
                      <p className="mt-2 text-[10px] text-slate-400">{hit.tags.join(" · ")}</p>
                    ) : null}
                  </button>
                </li>
              ))}
            </ul>
            {!hits.length ? (
              <p className="rounded-xl border border-slate-200 bg-white px-4 py-8 text-center text-sm text-slate-500">
                未找到匹配条目
              </p>
            ) : null}
          </>
        )}

        <p className="text-xs text-slate-400">
          也可在
          <Link to="/documents" className="mx-1 text-primary hover:underline">
            文档管理 · 条目视图
          </Link>
          内按库筛选检索
        </p>
      </div>
    </div>
  );
}
