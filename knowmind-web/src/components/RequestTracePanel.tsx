import { CheckCircle2, Circle, Loader2, SkipForward, XCircle } from "lucide-react";
import type { AgentStepEvent, AgentStepStatus } from "@/services/chat";

export type TraceStepRow = AgentStepEvent & {
  id: string;
  ts: number;
};

const STEP_LABELS: Record<string, string> = {
  conversation: "会话绑定",
  rag_retrieval: "知识库检索",
  web_search: "联网搜索",
  memory_retrieval: "对话记忆",
  file_tools: "文件工具",
  external_mcp: "外部 MCP",
  llm_generate: "模型生成",
  tool_call: "工具调用",
  error: "错误",
};

/** 不在追踪栏展示的步骤（思维链已在主对话区；其余为冗余状态） */
const HIDDEN_TRACE_STEPS = new Set([
  "thinking",
  "request",
  "prompt_assembly",
  "complete",
  "file_log",
]);

export function shouldShowTraceStep(ev: AgentStepEvent): boolean {
  if (HIDDEN_TRACE_STEPS.has(ev.step)) return false;
  if (ev.status === "skipped") return false;
  return true;
}

function stepLabel(step: string): string {
  return STEP_LABELS[step] ?? step;
}

function StatusIcon({ status }: { status: AgentStepStatus }) {
  if (status === "running") {
    return <Loader2 className="h-3.5 w-3.5 shrink-0 animate-spin text-primary" />;
  }
  if (status === "done") {
    return <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-600" />;
  }
  if (status === "error") {
    return <XCircle className="h-3.5 w-3.5 shrink-0 text-red-500" />;
  }
  if (status === "skipped") {
    return <SkipForward className="h-3.5 w-3.5 shrink-0 text-slate-400" />;
  }
  return <Circle className="h-3.5 w-3.5 shrink-0 text-slate-300" />;
}

/** 合并同 step 的 running 更新，以及 running → done/error。 */
export function upsertTraceStep(prev: TraceStepRow[], ev: AgentStepEvent): TraceStepRow[] {
  if (ev.status === "running") {
    for (let i = prev.length - 1; i >= 0; i--) {
      if (prev[i].step === ev.step && prev[i].status === "running") {
        const next = [...prev];
        next[i] = {
          ...next[i],
          detail: ev.detail ?? next[i].detail,
          meta: ev.meta ?? next[i].meta,
        };
        return next;
      }
    }
  }
  if (ev.status === "done" || ev.status === "error" || ev.status === "skipped") {
    for (let i = prev.length - 1; i >= 0; i--) {
      if (prev[i].step === ev.step && prev[i].status === "running") {
        const next = [...prev];
        next[i] = {
          ...next[i],
          status: ev.status,
          detail: ev.detail ?? next[i].detail,
          meta: ev.meta ?? next[i].meta,
        };
        return next;
      }
    }
  }
  return [
    ...prev,
    {
      ...ev,
      id: `${ev.step}-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
      ts: Date.now(),
    },
  ];
}

type RequestTracePanelProps = {
  traceId: string | null;
  kbName: string;
  steps: TraceStepRow[];
  loading: boolean;
};

function TraceStepItem({ row }: { row: TraceStepRow }) {
  return (
    <div className="flex items-start gap-2">
      <StatusIcon status={row.status} />
      <div className="min-w-0 flex-1">
        <div className="font-medium text-slate-800">{stepLabel(row.step)}</div>
        {row.detail ? (
          <p className="mt-0.5 line-clamp-2 break-words leading-relaxed text-slate-600">{row.detail}</p>
        ) : null}
      </div>
    </div>
  );
}

export function RequestTracePanel({ traceId, kbName, steps, loading }: RequestTracePanelProps) {
  return (
    <>
      <div className="border-b border-slate-100 p-4">
        <div className="break-all font-mono text-xs text-slate-600">{traceId ?? "—"}</div>
        <TraceHint />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-4">
        <TraceStepList steps={steps} loading={loading} />
      </div>
      <div className="border-t border-slate-100 p-4">
        <div className="text-xs font-semibold text-slate-500">当前知识库</div>
        <div className="mt-1 text-sm font-medium text-slate-900">{kbName}</div>
      </div>
    </>
  );
}

function TraceHint() {
  return (
    <div className="mt-2 text-xs text-slate-500">与后端 ChatResponse.trace_id 一致，可用于日志关联</div>
  );
}

function TraceStepList({ steps, loading }: { steps: TraceStepRow[]; loading: boolean }) {
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-700">Agent 步骤</p>
      {steps.length === 0 && !loading ? (
        <p className="rounded-lg border border-dashed border-slate-200 p-3 text-xs leading-relaxed text-slate-500">
          发送消息后，此处展示检索、工具调用与模型生成等关键步骤（不含推理正文，推理见左侧「思维链」）。
        </p>
      ) : (
        <ul className="space-y-2">
          {steps.map((row) => (
            <li
              key={row.id}
              className="rounded-lg border border-slate-100 bg-slate-50/80 px-3 py-2 text-xs text-slate-700"
            >
              <TraceStepItem row={row} />
            </li>
          ))}
        </ul>
      )}
      {loading && steps.length === 0 ? (
        <p className="flex items-center gap-2 text-xs text-slate-500">
          <Loader2 className="h-3.5 w-3.5 animate-spin" />
          等待首个步骤…
        </p>
      ) : null}
    </div>
  );
}
