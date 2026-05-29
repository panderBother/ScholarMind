import { Link2, Sparkles } from "lucide-react";
import { useNavigate } from "react-router-dom";

type Props = {
  kbId: string;
  className?: string;
};

/** 文档/知识库页共用的「知识生产」快捷入口 */
export function KnowledgeProductionActions({ kbId, className = "" }: Props) {
  const nav = useNavigate();
  if (!kbId) return null;

  return (
    <div
      className={`flex flex-wrap gap-2 rounded-xl border border-slate-200 bg-gradient-to-br from-slate-50 to-white p-3 ${className}`}
    >
      <span className="w-full text-[11px] font-semibold uppercase tracking-wide text-slate-400 lg:w-auto lg:self-center">
        知识生产
      </span>
      <button
        type="button"
        onClick={() => nav(`/production?kb_id=${encodeURIComponent(kbId)}&tab=url`)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-sky-200 bg-sky-50 px-3 py-1.5 text-xs font-medium text-sky-900 hover:bg-sky-100"
      >
        <Link2 className="h-3.5 w-3.5" />
        URL 采集
      </button>
      <button
        type="button"
        onClick={() => nav(`/production?kb_id=${encodeURIComponent(kbId)}&tab=distill`)}
        className="inline-flex items-center gap-1.5 rounded-lg border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-900 hover:bg-violet-100"
      >
        <Sparkles className="h-3.5 w-3.5" />
        缺口蒸馏
      </button>
    </div>
  );
}
