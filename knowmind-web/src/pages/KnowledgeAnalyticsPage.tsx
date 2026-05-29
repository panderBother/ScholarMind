import { useCallback, useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, BarChart3, Loader2, Sparkles } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import {
  fetchAnalyticsOverview,
  fetchAnalyticsTopItems,
  fetchAnalyticsTrend,
  type AnalyticsOverviewDto,
  type TopItemDto,
  type TrendPointDto,
} from "@/services/analytics";
import { getAccessToken } from "@/services/auth";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";

function formatDayLabel(iso: string): string {
  const d = iso.slice(5).replace("-", "/");
  return d;
}

/**
 * 知识库使用热度看板：概览 KPI、按日趋势折线、Top 条目柱状图。
 */
export function KnowledgeAnalyticsPage() {
  const { kbId: routeKbId } = useParams<{ kbId: string }>();
  const nav = useNavigate();
  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [kbId, setKbId] = useState(routeKbId ?? "");
  const [days, setDays] = useState<7 | 30>(7);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [overview, setOverview] = useState<AnalyticsOverviewDto | null>(null);
  const [topItems, setTopItems] = useState<TopItemDto[]>([]);
  const [trend, setTrend] = useState<TrendPointDto[]>([]);

  const kbName = useMemo(
    () => kbs.find((k) => k.id === kbId)?.name ?? "知识库",
    [kbs, kbId],
  );

  const loadKbs = useCallback(async () => {
    if (!getAccessToken()) {
      nav("/login", { replace: true });
      return;
    }
    const rows = await listKnowledgeBases();
    setKbs(rows);
    setKbId((cur) => cur || routeKbId || rows[0]?.id || "");
  }, [nav, routeKbId]);

  const loadAnalytics = useCallback(async () => {
    if (!kbId) return;
    setLoading(true);
    setError(null);
    try {
      const [ov, top, tr] = await Promise.all([
        fetchAnalyticsOverview(kbId, days),
        fetchAnalyticsTopItems(kbId, days, 10),
        fetchAnalyticsTrend(kbId, days),
      ]);
      setOverview(ov);
      setTopItems(top);
      setTrend(tr.points);
    } catch (e) {
      setError(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbId, days]);

  useEffect(() => {
    void loadKbs().catch((e) => {
      setError(e instanceof Error ? e.message : "加载知识库失败");
    });
  }, [loadKbs]);

  useEffect(() => {
    void loadAnalytics();
  }, [loadAnalytics]);

  useEffect(() => {
    if (kbId && kbId !== routeKbId) {
      nav(`/knowledge-bases/${kbId}/analytics`, { replace: true });
    }
  }, [kbId, routeKbId, nav]);

  const trendChart = useMemo(
    () =>
      trend.map((p) => ({
        ...p,
        label: formatDayLabel(p.date),
      })),
    [trend],
  );

  const topChart = useMemo(
    () =>
      topItems.map((item) => ({
        name: item.title.length > 12 ? `${item.title.slice(0, 12)}…` : item.title,
        fullTitle: item.title,
        count: item.count,
        search: item.search_hits,
        rag: item.rag_cites,
      })),
    [topItems],
  );

  return (
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 pb-6 lg:space-y-6 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="flex items-start gap-3">
          <Link
            to="/knowledge-bases"
            className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border border-slate-200 bg-white text-slate-600 hover:bg-slate-50"
            aria-label="返回知识库列表"
          >
            <ArrowLeft className="h-4 w-4" />
          </Link>
          <div>
            <div className="flex items-center gap-2 text-primary">
              <BarChart3 className="h-5 w-5" />
              <span className="text-xs font-semibold uppercase tracking-wide">热度统计</span>
            </div>
            <h1 className="mt-0.5 text-lg font-semibold text-slate-900 lg:text-xl">{kbName}</h1>
            <p className="mt-0.5 text-xs text-slate-500 lg:text-sm">
              检索命中、RAG 引用与对话轮次的真实使用数据
            </p>
          </div>
        </div>
        <div className="flex flex-wrap items-end gap-2 sm:gap-3">
          <label className="flex min-w-[140px] flex-1 flex-col gap-1 sm:flex-none">
            <span className="text-[11px] font-medium text-slate-500">知识库</span>
            <select
              value={kbId}
              onChange={(e) => setKbId(e.target.value)}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
            >
              {kbs.map((k) => (
                <option key={k.id} value={k.id}>
                  {k.name}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1">
            <span className="text-[11px] font-medium text-slate-500">时间范围</span>
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value) as 7 | 30)}
              className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-sm text-slate-800"
            >
              <option value={7}>最近 7 天</option>
              <option value={30}>最近 30 天</option>
            </select>
          </label>
        </div>
      </div>

      {error ? (
        <p className="rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">
          {error}
        </p>
      ) : null}

      {kbId && !loading && (overview?.search_hits ?? 0) + (overview?.rag_cites ?? 0) > 0 ? (
        <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-violet-200 bg-violet-50/80 px-4 py-3">
          <div className="min-w-0">
            <p className="text-sm font-medium text-violet-900">检索数据可用于缺口蒸馏</p>
            <p className="mt-0.5 text-xs text-violet-800/80">
              低命中或用户纠错会识别为知识缺口，并自动生成补全草稿。
            </p>
          </div>
          <Link
            to={`/production?kb_id=${encodeURIComponent(kbId)}&tab=distill`}
            className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-violet-600 px-3 py-2 text-xs font-semibold text-white hover:bg-violet-700"
          >
            <Sparkles className="h-3.5 w-3.5" />
            去缺口蒸馏
          </Link>
        </div>
      ) : null}

      {loading ? (
        <div className="flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载统计数据…
        </div>
      ) : (
        <>
          <section className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
            <KpiCard title="对话轮次" value={overview?.chat_turns ?? 0} hint="chat_turn" />
            <KpiCard title="检索命中" value={overview?.search_hits ?? 0} hint="search_hit" />
            <KpiCard title="RAG 引用" value={overview?.rag_cites ?? 0} hint="rag_cite" />
            <KpiCard title="活跃用户" value={overview?.unique_users ?? 0} hint="去重 user_id" />
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-card lg:rounded-xl lg:p-4">
            <h2 className="text-xs font-semibold text-slate-900 lg:text-sm">使用趋势（近 {days} 天）</h2>
            <div className="mt-3 h-56 lg:mt-4 lg:h-72">
              {trendChart.length === 0 ? (
                <p className="flex h-full items-center justify-center text-sm text-slate-400">
                  暂无使用记录，请先进行检索或对话
                </p>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart data={trendChart}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                    <XAxis dataKey="label" tick={{ fontSize: 11 }} />
                    <YAxis allowDecimals={false} tick={{ fontSize: 11 }} />
                    <Tooltip />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="search_hit"
                      name="检索命中"
                      stroke="#0066FF"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="rag_cite"
                      name="RAG 引用"
                      stroke="#10B981"
                      strokeWidth={2}
                      dot={false}
                    />
                    <Line
                      type="monotone"
                      dataKey="chat_turn"
                      name="对话轮次"
                      stroke="#F59E0B"
                      strokeWidth={2}
                      dot={false}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          </section>

          <section className="grid gap-3 lg:grid-cols-2 lg:gap-4">
            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl">
              <h2 className="text-sm font-semibold text-slate-900">事件汇总</h2>
              <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
                <div>
                  <dt className="text-xs text-slate-500">总事件数</dt>
                  <dd className="text-lg font-semibold tabular-nums text-slate-900">
                    {(overview?.total_events ?? 0).toLocaleString()}
                  </dd>
                </div>
                <div>
                  <dt className="text-xs text-slate-500">统计窗口</dt>
                  <dd className="text-lg font-semibold text-slate-900">近 {days} 天</dd>
                </div>
              </dl>
              <p className="mt-4 text-xs leading-relaxed text-slate-500">
                管理端混合检索产生「检索命中」；对话选用知识库时记录「对话轮次」；RAG 召回片段记为「RAG
                引用」。可在文档页检索或智能对话中积累数据。
              </p>
            </div>

            <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl">
              <h2 className="text-sm font-semibold text-slate-900">热门知识条目 Top 10</h2>
              <div className="mt-3 h-52 lg:mt-4 lg:h-64">
                {topChart.length === 0 ? (
                  <p className="flex h-full items-center justify-center text-sm text-slate-400">
                    暂无条目热度数据
                  </p>
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={topChart} layout="vertical" margin={{ left: 8, right: 16 }}>
                      <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                      <XAxis type="number" allowDecimals={false} tick={{ fontSize: 10 }} />
                      <YAxis
                        type="category"
                        dataKey="name"
                        width={72}
                        tick={{ fontSize: 10 }}
                      />
                      <Tooltip
                        formatter={(value, name) => [value, name === "search" ? "检索" : "RAG"]}
                        labelFormatter={(_, payload) =>
                          payload?.[0]?.payload?.fullTitle ?? ""
                        }
                      />
                      <Legend />
                      <Bar dataKey="search" name="检索命中" stackId="a" fill="#0066FF" radius={[0, 0, 0, 0]} />
                      <Bar dataKey="rag" name="RAG 引用" stackId="a" fill="#10B981" radius={[0, 4, 4, 0]} />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </div>
            </div>
          </section>

          {topItems.length > 0 ? (
            <section className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl">
              <h2 className="text-sm font-semibold text-slate-900">条目明细</h2>
              <ul className="mt-3 divide-y divide-slate-100">
                {topItems.map((item, idx) => (
                  <li key={item.item_id} className="flex items-center gap-3 py-3 text-sm">
                    <span className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-100 text-xs font-bold text-slate-600">
                      {idx + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <p className="truncate font-medium text-slate-900">{item.title}</p>
                      <p className="text-xs text-slate-500">
                        检索 {item.search_hits} · RAG {item.rag_cites}
                      </p>
                    </div>
                    <span className="shrink-0 font-semibold tabular-nums text-primary">
                      {item.count}
                    </span>
                  </li>
                ))}
              </ul>
            </section>
          ) : null}
        </>
      )}
    </div>
  );
}

function KpiCard({
  title,
  value,
  hint,
}: {
  title: string;
  value: number;
  hint: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-card lg:rounded-xl lg:p-4">
      <div className="text-xs font-semibold text-slate-900">{title}</div>
      <div className="text-[10px] text-slate-400">{hint}</div>
      <div className="mt-2 text-xl font-bold tabular-nums text-slate-900 lg:text-2xl">
        {value.toLocaleString()}
      </div>
    </div>
  );
}
