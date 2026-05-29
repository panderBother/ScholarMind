import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink, Loader2, Sparkles } from "lucide-react";

import { useUi } from "@/components/ui/UiProvider";
import {
  analyzeKnowledgeGaps,
  generateGapDrafts,
  listKnowledgeGaps,
  type KnowledgeGapDto,
} from "@/services/distill";

const RULE_LABEL: Record<string, string> = {
  high_miss: "高频低命中",
  user_correction: "用户纠错",
};

const STATUS_LABEL: Record<string, string> = {
  open: "待补全",
  draft_generated: "已生成草稿",
};

type Props = {
  kbId: string;
  onChanged?: () => void;
  /** modal：弹层；page：知识生产页内嵌 */
  variant?: "modal" | "page";
  onClose?: () => void;
};

export function KnowledgeGapsPanel({ kbId, onChanged, variant = "page", onClose }: Props) {
  const nav = useNavigate();
  const { message } = useUi();
  const [gaps, setGaps] = useState<KnowledgeGapDto[]>([]);
  const [loading, setLoading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [generatingId, setGeneratingId] = useState<string | null>(null);
  const [err, setErr] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const rows = await listKnowledgeGaps(kbId);
      setGaps(rows);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, [kbId]);

  useEffect(() => {
    void load();
  }, [load]);

  const onAnalyze = async () => {
    setAnalyzing(true);
    setErr(null);
    try {
      await analyzeKnowledgeGaps(kbId);
      await load();
      message.success("分析完成，已更新缺口列表");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "分析失败");
    } finally {
      setAnalyzing(false);
    }
  };

  const onGenerate = async (gap: KnowledgeGapDto) => {
    if (gap.status === "draft_generated" && gap.draft_item_ids?.length) {
      nav(`/documents/items/${kbId}/${gap.draft_item_ids[0]}`);
      return;
    }
    setGeneratingId(gap.id);
    setErr(null);
    try {
      const res = await generateGapDrafts(kbId, gap.id);
      await load();
      onChanged?.();
      const n = res.drafts?.length ?? 0;
      message.success(n > 0 ? `已生成 ${n} 条草稿，请在条目视图中审核发布` : "草稿已生成");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "生成草稿失败");
    } finally {
      setGeneratingId(null);
    }
  };

  const body = (
    <>
      <div className="mb-4 rounded-xl border border-violet-100 bg-violet-50/60 px-4 py-3 text-xs leading-relaxed text-violet-900">
        <p className="font-semibold">使用步骤</p>
        <ol className="mt-1.5 list-inside list-decimal space-y-0.5 text-violet-800/90">
          <li>在「智能对话」中选择本库提问（尤其库内尚未覆盖的话题）</li>
          <li>对不满意的回答可点「不满意 / 纠错」提交反馈</li>
          <li>回到此处点击「分析缺口」，再为每条缺口「生成草稿条目」</li>
          <li>在文档管理 → 条目视图审核草稿并发布</li>
        </ol>
      </div>

      {err ? <p className="mb-3 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700">{err}</p> : null}

      <div className="mb-4 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => void onAnalyze()}
          disabled={analyzing || loading}
          className="inline-flex items-center gap-1.5 rounded-lg bg-violet-600 px-4 py-2 text-sm font-semibold text-white disabled:opacity-50"
        >
          {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
          {analyzing ? "分析中…" : "分析缺口"}
        </button>
        <button
          type="button"
          onClick={() => void load()}
          disabled={loading}
          className="rounded-lg border border-slate-200 px-4 py-2 text-sm text-slate-700 hover:bg-slate-50"
        >
          刷新列表
        </button>
        {variant === "page" ? (
          <button
            type="button"
            onClick={() => nav("/chat")}
            className="rounded-lg border border-primary/30 bg-primary/5 px-4 py-2 text-sm font-medium text-primary"
          >
            去对话积累数据
          </button>
        ) : null}
      </div>

      {loading && gaps.length === 0 ? (
        <p className="flex items-center gap-2 py-8 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
        </p>
      ) : gaps.length === 0 ? (
        <p className="rounded-xl border border-dashed border-slate-200 bg-slate-50 px-4 py-10 text-center text-sm text-slate-500">
          暂无缺口记录。先进行几轮对话或提交纠错，再点击「分析缺口」。
        </p>
      ) : (
        <ul className="space-y-3">
          {gaps.map((g) => (
            <li key={g.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-violet-100 px-2 py-0.5 text-xs font-medium text-violet-800">
                  {RULE_LABEL[g.trigger_rule] ?? g.trigger_rule}
                </span>
                <span
                  className={
                    g.status === "draft_generated"
                      ? "rounded-full bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800"
                      : "rounded-full bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800"
                  }
                >
                  {STATUS_LABEL[g.status] ?? g.status}
                </span>
                {g.avg_score != null ? (
                  <span className="text-xs text-slate-500">平均相关度 {g.avg_score.toFixed(2)}</span>
                ) : null}
                <span className="text-xs text-slate-400">样本 ×{g.hit_count}</span>
              </div>
              <ul className="mt-2 list-inside list-disc space-y-0.5 text-xs text-slate-600">
                {(g.sample_queries || []).slice(0, 5).map((q) => (
                  <li key={q} className="line-clamp-2">
                    {q}
                  </li>
                ))}
              </ul>
              {g.draft_item_ids && g.draft_item_ids.length > 0 ? (
                <div className="mt-3 flex flex-wrap gap-2">
                  {g.draft_item_ids.map((itemId) => (
                    <button
                      key={itemId}
                      type="button"
                      onClick={() => nav(`/documents/items/${kbId}/${itemId}`)}
                      className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:underline"
                    >
                      <ExternalLink className="h-3 w-3" />
                      查看草稿 {itemId.slice(0, 8)}…
                    </button>
                  ))}
                </div>
              ) : null}
              <button
                type="button"
                disabled={generatingId === g.id}
                onClick={() => void onGenerate(g)}
                className="mt-3 text-xs font-semibold text-primary hover:underline disabled:opacity-50"
              >
                {generatingId === g.id
                  ? "生成中…"
                  : g.status === "draft_generated"
                    ? "再次打开草稿"
                    : "生成草稿条目"}
              </button>
            </li>
          ))}
        </ul>
      )}
    </>
  );

  if (variant === "modal") {
    return (
      <div className="fixed inset-0 z-50 flex items-end justify-center bg-black/40 p-4 lg:items-center">
        <div className="flex max-h-[90vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl bg-white shadow-xl">
          <div className="flex items-center justify-between border-b px-4 py-3">
            <div>
              <h2 className="font-semibold text-slate-900">知识缺口蒸馏</h2>
              <p className="text-xs text-slate-500">基于检索日志与用户纠错</p>
            </div>
            {onClose ? (
              <button type="button" onClick={onClose} className="text-sm text-slate-500">
                关闭
              </button>
            ) : null}
          </div>
          <div className="flex-1 overflow-y-auto p-4">{body}</div>
        </div>
      </div>
    );
  }

  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:p-6">
      <div className="mb-4">
        <h2 className="text-sm font-semibold text-slate-900">知识缺口蒸馏</h2>
        <p className="mt-1 text-xs text-slate-500">从对话检索与用户反馈中识别知识盲区，并 AI 生成补全草稿</p>
      </div>
      {body}
    </div>
  );
}
