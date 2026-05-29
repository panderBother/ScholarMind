import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Bot, Loader2, Plus, RefreshCw, Trash2 } from "lucide-react";
import { useUi } from "@/components/ui/UiProvider";
import { createExpert, deleteExpert, listExperts, refreshExpert, type ExpertDto } from "@/services/experts";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";

export function ExpertsPage() {
  const nav = useNavigate();
  const { confirm, message } = useUi();
  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [experts, setExperts] = useState<ExpertDto[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [selectedKb, setSelectedKb] = useState("");
  const [expertName, setExpertName] = useState("");
  const [showCreate, setShowCreate] = useState(false);

  const kbName = (id: string) => kbs.find((k) => k.id === id)?.name ?? id.slice(0, 8);

  const load = useCallback(async () => {
    setLoading(true);
    setErr(null);
    try {
      const [kbRows, expertRows] = await Promise.all([listKnowledgeBases(), listExperts()]);
      setKbs(kbRows);
      setExperts(expertRows);
      setSelectedKb((prev) => prev || kbRows[0]?.id || "");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "加载失败");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const handleCreate = async () => {
    if (!selectedKb) {
      setErr("请先选择知识库");
      return;
    }
    setCreating(true);
    setErr(null);
    try {
      const row = await createExpert({
        kb_id: selectedKb,
        name: expertName.trim() || undefined,
      });
      message.success("专家已创建");
      setShowCreate(false);
      setExpertName("");
      await load();
      nav(`/experts/${row.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "创建失败");
    } finally {
      setCreating(false);
    }
  };

  const handleRefresh = async (id: string) => {
    try {
      await refreshExpert(id);
      message.success("已根据最新已发布条目更新人设");
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "更新失败");
    }
  };

  const handleDelete = async (ex: ExpertDto) => {
    const ok = await confirm({
      title: "删除专家",
      message: `确定删除「${ex.name}」？此操作不可恢复。`,
    });
    if (!ok) return;
    try {
      await deleteExpert(ex.id);
      await load();
    } catch (e) {
      setErr(e instanceof Error ? e.message : "删除失败");
    }
  };

  return (
    <div className="min-h-0 flex-1 overflow-y-auto p-4 pb-6 lg:p-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-semibold text-slate-900 lg:text-xl">专家 Agent</h1>
          <p className="mt-1 max-w-2xl text-xs text-slate-600 lg:text-sm">
            按知识库已发布条目一键生成领域专家，独立对话流 + RAG 检索。
          </p>
        </div>
        <button
          type="button"
          onClick={() => setShowCreate((v) => !v)}
          className="inline-flex items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-white shadow-sm hover:bg-primary-hover"
        >
          <Plus className="h-4 w-4" />
          创建专家
        </button>
      </div>

      {err ? (
        <p className="mt-3 rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-xs text-red-700">{err}</p>
      ) : null}

      {showCreate ? (
        <div className="mt-4 rounded-2xl border border-slate-200 bg-slate-50/80 p-4 lg:rounded-xl">
          <p className="text-xs font-medium text-slate-700">选择知识库并生成专家人设</p>
          <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-slate-600">
              知识库
              <select
                value={selectedKb}
                onChange={(e) => setSelectedKb(e.target.value)}
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              >
                {kbs.map((k) => (
                  <option key={k.id} value={k.id}>
                    {k.name}
                  </option>
                ))}
              </select>
            </label>
            <label className="flex min-w-0 flex-1 flex-col gap-1 text-xs text-slate-600">
              专家名称（可选）
              <input
                value={expertName}
                onChange={(e) => setExpertName(e.target.value)}
                placeholder="默认：{知识库名} 专家"
                className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm"
              />
            </label>
            <button
              type="button"
              disabled={creating || !selectedKb}
              onClick={() => void handleCreate()}
              className="rounded-lg bg-primary px-4 py-2 text-xs font-semibold text-white disabled:opacity-50"
            >
              {creating ? "生成中…" : "确认创建"}
            </button>
          </div>
        </div>
      ) : null}

      {loading ? (
        <p className="mt-8 flex items-center gap-2 text-sm text-slate-500">
          <Loader2 className="h-4 w-4 animate-spin" /> 加载中…
        </p>
      ) : experts.length === 0 ? (
        <p className="mt-8 rounded-xl border border-dashed border-slate-200 bg-white px-4 py-10 text-center text-sm text-slate-500">
          暂无专家。请先发布知识库条目，再点击「创建专家」。
        </p>
      ) : (
        <div className="mt-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {experts.map((ex) => (
            <article
              key={ex.id}
              className="flex flex-col rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:rounded-xl"
            >
              <div className="flex items-start gap-3">
                <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-violet-100 text-violet-700">
                  <Bot className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <h2 className="truncate text-sm font-semibold text-slate-900">{ex.name}</h2>
                  <p className="mt-0.5 text-[11px] text-slate-500">知识库：{kbName(ex.kb_id)}</p>
                  {ex.description ? (
                    <p className="mt-2 line-clamp-2 text-xs text-slate-600">{ex.description}</p>
                  ) : null}
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => nav(`/experts/${ex.id}`)}
                  className="rounded-lg bg-primary px-3 py-1.5 text-xs font-semibold text-white hover:bg-primary-hover"
                >
                  开始对话
                </button>
                <button
                  type="button"
                  onClick={() => void handleRefresh(ex.id)}
                  className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1.5 text-xs text-slate-600 hover:bg-slate-50"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  更新人设
                </button>
                <button
                  type="button"
                  onClick={() => void handleDelete(ex)}
                  className="inline-flex items-center gap-1 rounded-lg border border-red-100 px-2.5 py-1.5 text-xs text-red-600 hover:bg-red-50"
                >
                  <Trash2 className="h-3.5 w-3.5" />
                  删除
                </button>
              </div>
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
