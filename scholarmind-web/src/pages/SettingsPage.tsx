import { BarChart3, ChevronRight, Wrench } from "lucide-react";
import { Link } from "react-router-dom";

/**
 * 我的 / 设置：移动端底部「我的」入口；提供评估看板、工具等次级入口（主导航为 5 Tab 时的补偿）。
 */
export function SettingsPage() {
  return (
    <div className="p-4 pb-6 lg:p-8">
      <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">我的</h1>
      <p className="mt-1 text-xs text-slate-500 lg:text-sm">账户、模型与扩展能力入口</p>

      <ul className="mt-4 space-y-2 lg:mt-6">
        <li>
          <Link
            to="/evaluation"
            className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3.5 text-sm font-medium text-slate-800 shadow-card active:bg-slate-50 lg:rounded-xl"
          >
            <span className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-primary-soft text-primary">
                <BarChart3 className="h-5 w-5" />
              </span>
              RAG 评估看板
            </span>
            <ChevronRight className="h-4 w-4 text-slate-400" />
          </Link>
        </li>
        <li>
          <Link
            to="/tools"
            className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3.5 text-sm font-medium text-slate-800 shadow-card active:bg-slate-50 lg:rounded-xl"
          >
            <span className="flex items-center gap-3">
              <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-slate-100 text-slate-700">
                <Wrench className="h-5 w-5" />
              </span>
              工具与 MCP
            </span>
            <ChevronRight className="h-4 w-4 text-slate-400" />
          </Link>
        </li>
      </ul>

      <div className="mt-6 max-w-lg rounded-2xl border border-slate-200 bg-white p-4 text-sm text-slate-600 shadow-card lg:rounded-xl lg:p-6">
        <p className="text-xs lg:text-sm">更多账户、模型路由与数据保留策略等表单将在鉴权与用户表就绪后补充。</p>
      </div>
    </div>
  );
}
