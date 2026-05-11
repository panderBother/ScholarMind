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

const TREND = [
  { t: "4/10", faith: 82, rel: 88, recall: 76, prec: 80 },
  { t: "4/15", faith: 84, rel: 87, recall: 78, prec: 81 },
  { t: "4/20", faith: 86, rel: 90, recall: 79, prec: 83 },
  { t: "4/25", faith: 88, rel: 91, recall: 81, prec: 85 },
  { t: "5/1", faith: 90, rel: 92, recall: 83, prec: 86 },
];

const VERSION_CMP = [
  { name: "忠实度", v21: 90, v20: 84 },
  { name: "答案相关性", v21: 92, v20: 88 },
  { name: "上下文召回", v21: 83, v20: 78 },
  { name: "上下文精准", v21: 86, v20: 81 },
];

/**
 * RAG 评估看板：筛选器、四象限 KPI、时序折线、版本对比柱状图。
 * 指标数据后续由 scholarmind-eval 流水线产出并写入 API。
 */
export function EvalDashboardPage() {
  return (
    <div className="min-h-0 flex-1 space-y-4 overflow-y-auto p-4 pb-6 lg:space-y-6 lg:p-8">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between lg:items-end">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">RAG 评估看板</h1>
          <p className="mt-0.5 text-xs text-slate-500 lg:text-sm">RAGAS 指标趋势与版本对比（示意）</p>
        </div>
        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row sm:flex-wrap sm:gap-3">
          <FilterSelect label="时间范围" value="最近 30 天" />
          <FilterSelect label="知识库" value="全部" />
          <FilterSelect label="版本对比" value="v2.1.0 vs v2.0.0" />
        </div>
      </div>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
        <KpiCard title="忠实度" sub="Faithfulness" value="0.89" delta="+0.05" positive />
        <KpiCard title="答案相关性" sub="Answer Relevancy" value="0.92" delta="+0.03" positive />
        <KpiCard title="上下文召回" sub="Context Recall" value="0.83" delta="-0.01" />
        <KpiCard title="上下文精准" sub="Context Precision" value="0.86" delta="+0.04" positive />
      </section>

      <section className="rounded-2xl border border-slate-200 bg-white p-3 shadow-card lg:rounded-xl lg:p-4">
        <h2 className="text-xs font-semibold text-slate-900 lg:text-sm">指标趋势</h2>
        <div className="mt-3 h-56 lg:mt-4 lg:h-72">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={TREND}>
              <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
              <XAxis dataKey="t" tick={{ fontSize: 11 }} />
              <YAxis domain={[60, 100]} tick={{ fontSize: 11 }} />
              <Tooltip />
              <Legend />
              <Line type="monotone" dataKey="faith" name="忠实度" stroke="#0066FF" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="rel" name="答案相关性" stroke="#10B981" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="recall" name="上下文召回" stroke="#F59E0B" strokeWidth={2} dot={false} />
              <Line type="monotone" dataKey="prec" name="上下文精准" stroke="#6366F1" strokeWidth={2} dot={false} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </section>

      <section className="grid gap-3 lg:grid-cols-2 lg:gap-4">
        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl">
          <h2 className="text-sm font-semibold text-slate-900">数据统计</h2>
          <dl className="mt-4 grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="text-xs text-slate-500">总评估次数</dt>
              <dd className="text-lg font-semibold text-slate-900">1,248</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">问题数量</dt>
              <dd className="text-lg font-semibold text-slate-900">320</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">平均响应时延</dt>
              <dd className="text-lg font-semibold text-slate-900">1.9s</dd>
            </div>
            <div>
              <dt className="text-xs text-slate-500">通过率</dt>
              <dd className="text-lg font-semibold text-slate-900">94.2%</dd>
            </div>
          </dl>
        </div>

        <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl">
          <h2 className="text-sm font-semibold text-slate-900">版本对比（v2.1.0 vs v2.0.0）</h2>
          <div className="mt-3 h-52 lg:mt-4 lg:h-64">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={VERSION_CMP}>
                <CartesianGrid strokeDasharray="3 3" stroke="#E2E8F0" />
                <XAxis dataKey="name" tick={{ fontSize: 10 }} />
                <YAxis domain={[60, 100]} tick={{ fontSize: 10 }} />
                <Tooltip />
                <Legend />
                <Bar dataKey="v21" name="v2.1.0" fill="#0066FF" radius={[4, 4, 0, 0]} />
                <Bar dataKey="v20" name="v2.0.0" fill="#94A3B8" radius={[4, 4, 0, 0]} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </section>
    </div>
  );
}

function KpiCard({
  title,
  sub,
  value,
  delta,
  positive,
}: {
  title: string;
  sub: string;
  value: string;
  delta: string;
  positive?: boolean;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3 shadow-card lg:rounded-xl lg:p-4">
      <div className="text-xs font-semibold text-slate-900">{title}</div>
      <div className="text-[10px] text-slate-400">{sub}</div>
      <div className="mt-2 flex items-baseline justify-between gap-2">
        <div className="text-xl font-bold tabular-nums text-slate-900 lg:text-2xl">{value}</div>
        <div className={positive ? "text-xs font-semibold text-emerald-600" : "text-xs font-semibold text-amber-600"}>
          {delta}
        </div>
      </div>
    </div>
  );
}

function FilterSelect({ label, value }: { label: string; value: string }) {
  return (
    <label className="flex flex-col gap-1">
      <span className="text-[11px] font-medium text-slate-500">{label}</span>
      <select className="rounded-lg border border-slate-200 bg-white px-2 py-1.5 text-slate-800">
        <option>{value}</option>
      </select>
    </label>
  );
}
