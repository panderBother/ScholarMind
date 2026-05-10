import { Link } from "react-router-dom";

const MOCK = [
  { id: "rpt-001", title: "多模态基础模型方法综述", updated: "2026-05-02" },
  { id: "rpt-002", title: "联邦学习隐私风险清单", updated: "2026-04-29" },
];

/** 报告列表入口：点击跳转报告详情与溯源页 */
export function ReportsIndexPage() {
  return (
    <div className="p-4 pb-6 lg:p-8">
      <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">报告</h1>
      <p className="mt-1 text-xs text-slate-500 lg:text-sm">由 Agent 生成的结构化研究报告</p>
      <ul className="mt-4 divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white shadow-card lg:mt-6 lg:rounded-xl">
        {MOCK.map((r) => (
          <li
            key={r.id}
            className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:text-sm hover:bg-slate-50"
          >
            <div className="min-w-0">
              <div className="font-medium leading-snug text-slate-900">{r.title}</div>
              <div className="mt-0.5 text-xs text-slate-500">更新于 {r.updated}</div>
            </div>
            <Link
              to={`/reports/${r.id}`}
              className="inline-flex shrink-0 justify-center rounded-xl bg-primary px-4 py-2 text-center text-xs font-semibold text-white hover:bg-primary-hover sm:rounded-lg sm:py-1.5"
            >
              打开
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
