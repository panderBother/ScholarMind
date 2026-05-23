import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Loader2, Trash2 } from "lucide-react";

import { useUi } from "@/components/ui/UiProvider";
import { deleteReport, listReports, type ResearchReportListItemDto } from "@/services/reports";

/** 报告列表 */
export function ReportsIndexPage() {
  const { confirm, message } = useUi();
  const [rows, setRows] = useState<ResearchReportListItemDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      setRows(await listReports());
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const onDelete = async (r: ResearchReportListItemDto) => {
    const ok = await confirm({
      title: "删除报告",
      message: `确定删除「${r.title}」？`,
      confirmText: "删除",
      type: "danger",
    });
    if (!ok) return;
    setDeletingId(r.id);
    try {
      await deleteReport(r.id);
      message.success("已删除");
      setRows((prev) => prev.filter((x) => x.id !== r.id));
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    } finally {
      setDeletingId(null);
    }
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-6 lg:p-8">
      <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">报告</h1>
      <p className="mt-1 text-xs text-slate-500 lg:text-sm">
        由对话一键生成的结构化研究报告，点击引用可查看知识库原文
      </p>

      {err ? <p className="mt-4 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p> : null}

      {loading ? (
        <div className="mt-8 flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" />
          加载中…
        </div>
      ) : rows.length === 0 ? (
        <p className="mt-8 text-sm text-slate-500">
          暂无报告。在「对话」页完成一轮问答后，点击「生成报告」即可创建。
        </p>
      ) : (
        <ul className="mt-4 divide-y divide-slate-100 rounded-2xl border border-slate-200 bg-white shadow-card lg:mt-6 lg:rounded-xl">
          {rows.map((r) => (
            <li
              key={r.id}
              className="flex flex-col gap-2 px-4 py-3 sm:flex-row sm:items-center sm:justify-between sm:text-sm hover:bg-slate-50"
            >
              <div className="min-w-0 flex-1">
                <div className="font-medium leading-snug text-slate-900">{r.title}</div>
                {r.summary ? (
                  <p className="mt-1 line-clamp-2 text-xs text-slate-500">{r.summary}</p>
                ) : null}
                <div className="mt-1 text-xs text-slate-400">
                  更新于 {new Date(r.updated_at).toLocaleString()} · {r.citation_count} 条引用
                </div>
              </div>
              <div className="flex shrink-0 gap-2">
                <button
                  type="button"
                  disabled={deletingId === r.id}
                  onClick={() => void onDelete(r)}
                  className="inline-flex items-center justify-center rounded-xl border border-red-200 px-3 py-2 text-red-600 hover:bg-red-50 disabled:opacity-50 sm:rounded-lg sm:py-1.5"
                  title="删除"
                >
                  {deletingId === r.id ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <Trash2 className="h-4 w-4" />
                  )}
                </button>
                <Link
                  to={`/reports/${r.id}`}
                  className="inline-flex justify-center rounded-xl bg-primary px-4 py-2 text-center text-xs font-semibold text-white hover:bg-primary-hover sm:rounded-lg sm:py-1.5"
                >
                  打开
                </Link>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
