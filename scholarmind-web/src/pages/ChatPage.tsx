import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  ChevronDown,
  ChevronRight,
  Loader2,
  Plus,
  Send,
  Sparkles,
  SquarePen,
} from "lucide-react";
import { AssistantMarkdown } from "@/components/AssistantMarkdown";
import { getAccessToken } from "@/services/auth";
import { streamChatMessage } from "@/services/chat";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";
import { mergeThinkingParts, partitionThinkingBlocks } from "@/utils/partitionThinking";

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  trace_id?: string;
  /** false：SSE 未结束，交给 Streamdown 的流式模式 */
  streamFinal?: boolean;
  /** DeepSeek-R1 等返回的推理过程（SSE thinking_delta） */
  thinkingContent?: string;
};

/**
 * 对话与研究：`POST /api/v1/chat/stream`（SSE）+ Streamdown（Shiki 高亮）；侧栏 trace_id。
 */
export function ChatPage() {
  const nav = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [kbId, setKbId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [deepResearch, setDeepResearch] = useState(true);
  const [webSearch, setWebSearch] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showThought, setShowThought] = useState(true);
  const [mobileKbOpen, setMobileKbOpen] = useState(false);

  const kbName = useMemo(() => kbs.find((k) => k.id === kbId)?.name ?? "选择知识库", [kbs, kbId]);

  const lastTraceId = useMemo(() => {
    for (let i = messages.length - 1; i >= 0; i--) {
      if (messages[i].role === "assistant" && messages[i].trace_id) {
        return messages[i].trace_id;
      }
    }
    return null;
  }, [messages]);

  const loadKbs = useCallback(async () => {
    if (!getAccessToken()) {
      nav("/login", { replace: true });
      return;
    }
    try {
      const rows = await listKnowledgeBases();
      setKbs(rows);
      setKbId((cur) => cur || rows[0]?.id || "");
    } catch {
      setErr("无法加载知识库，请稍后重试");
    }
  }, [nav]);

  useEffect(() => {
    void loadKbs();
  }, [loadKbs]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading) return;
    setErr(null);
    setInput("");
    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: "user",
      content: text,
    };
    const assistantId = crypto.randomUUID();
    const assistantPlaceholder: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "",
      streamFinal: false,
    };
    setMessages((m) => [...m, userMsg, assistantPlaceholder]);
    setLoading(true);
    let acc = "";
    let thinkingAcc = "";
    let streamFailed = false;
    try {
      await streamChatMessage(
        {
          message: text,
          knowledge_base_id: kbId || null,
          deep_research: deepResearch,
          web_search: webSearch,
        },
        {
          onTraceId: (traceId) => {
            setMessages((m) =>
              m.map((row) => (row.id === assistantId ? { ...row, trace_id: traceId } : row)),
            );
          },
          onThinkingDelta: (chunk) => {
            thinkingAcc += chunk;
            const { visible, thinking: tagThinking } = partitionThinkingBlocks(acc);
            const thinkingContent = mergeThinkingParts(thinkingAcc, tagThinking);
            setMessages((m) =>
              m.map((row) =>
                row.id === assistantId
                  ? { ...row, content: visible, thinkingContent, streamFinal: false }
                  : row,
              ),
            );
          },
          onDelta: (chunk) => {
            acc += chunk;
            const { visible, thinking: tagThinking } = partitionThinkingBlocks(acc);
            const thinkingContent = mergeThinkingParts(thinkingAcc, tagThinking);
            setMessages((m) =>
              m.map((row) =>
                row.id === assistantId
                  ? { ...row, content: visible, thinkingContent, streamFinal: false }
                  : row,
              ),
            );
          },
          onError: (msg) => {
            streamFailed = true;
            setErr(msg);
            const { thinking: tagThinking } = partitionThinkingBlocks(acc);
            const thinkingContent = mergeThinkingParts(thinkingAcc, tagThinking);
            setMessages((m) =>
              m.map((row) =>
                row.id === assistantId
                  ? {
                      ...row,
                      content: `**调用失败** ${msg}`,
                      streamFinal: true,
                      thinkingContent,
                    }
                  : row,
              ),
            );
          },
          onDone: () => {
            if (!streamFailed) {
              const { visible, thinking: tagThinking } = partitionThinkingBlocks(acc);
              const thinkingContent = mergeThinkingParts(thinkingAcc, tagThinking);
              setMessages((m) =>
                m.map((row) =>
                  row.id === assistantId
                    ? { ...row, content: visible, streamFinal: true, thinkingContent }
                    : row,
                ),
              );
            }
          },
        },
      );
    } catch (e) {
      const { visible: visibleAcc } = partitionThinkingBlocks(acc);
      const msg = e instanceof Error ? e.message : "发送失败";
      setErr(msg);
      const mdBody = visibleAcc
        ? `**已中断**（${msg}）\n\n---\n\n${visibleAcc}`
        : `**请求失败** ${msg}`;
      setMessages((m) =>
        m.map((row) =>
          row.id === assistantId
            ? { ...row, content: mdBody, streamFinal: true }
            : row,
        ),
      );
    } finally {
      setLoading(false);
    }
  };

  const newChat = () => {
    setMessages([]);
    setErr(null);
    setInput("");
  };

  const appendPrompt = (t: string) => {
    setInput((prev) => (prev ? `${prev}\n${t}` : t));
  };

  return (
    <div className="flex h-full min-h-0 flex-col lg:flex-row">
      <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-200 bg-white lg:flex">
        <div className="flex items-center justify-between border-b border-slate-100 p-3">
          <span className="text-xs font-semibold uppercase tracking-wide text-slate-400">知识库</span>
          <button
            type="button"
            onClick={newChat}
            className="text-xs font-medium text-primary hover:underline"
          >
            新对话
          </button>
        </div>
        <ul className="flex-1 space-y-1 overflow-y-auto p-2 text-sm">
          {kbs.length === 0 ? (
            <li className="px-2 py-2 text-xs text-slate-500">暂无知识库，请先在「知识库」中创建</li>
          ) : (
            kbs.map((k) => (
              <li key={k.id}>
                <button
                  type="button"
                  onClick={() => setKbId(k.id)}
                  className={
                    k.id === kbId
                      ? "flex w-full items-center gap-2 rounded-lg bg-primary-soft px-2 py-2 text-left font-medium text-primary"
                      : "flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-slate-700 hover:bg-slate-50"
                  }
                >
                  <BookOpen className="h-4 w-4 shrink-0 text-primary" />
                  <span className="line-clamp-2">{k.name}</span>
                </button>
              </li>
            ))
          )}
        </ul>
        <div className="border-t border-slate-100 p-3">
          <div className="mb-2 text-xs font-semibold text-slate-500">知识图谱（示意）</div>
          <div className="relative h-40 rounded-lg bg-slate-50 p-2 text-[10px] text-slate-500">
            <div className="absolute left-6 top-6 rounded-md bg-white px-2 py-1 shadow">实体 A</div>
            <div className="absolute right-8 top-10 rounded-md bg-white px-2 py-1 shadow">实体 B</div>
            <div className="absolute bottom-8 left-10 rounded-md bg-primary-soft px-2 py-1 text-primary shadow">
              关系
            </div>
            <svg className="pointer-events-none absolute inset-0 h-full w-full">
              <line x1="40" y1="40" x2="120" y2="50" stroke="#CBD5E1" strokeWidth="1" />
            </svg>
          </div>
        </div>
      </aside>

      <section className="flex min-h-0 min-w-0 flex-1 flex-col bg-slate-50">
        <header className="flex items-center gap-2 border-b border-slate-200 bg-white px-3 py-2.5 lg:px-6 lg:py-3">
          <div className="relative min-w-0 flex-1 lg:hidden">
            <button
              type="button"
              onClick={() => setMobileKbOpen((v) => !v)}
              className="flex w-full items-center justify-between gap-2 rounded-xl border border-slate-200 bg-slate-50 px-3 py-2 text-left text-sm font-medium text-slate-800"
            >
              <span className="truncate">{kbName}</span>
              <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
            </button>
            {mobileKbOpen ? (
              <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-48 overflow-auto rounded-xl border border-slate-200 bg-white py-1 shadow-lg">
                {kbs.map((k) => (
                  <li key={k.id}>
                    <button
                      type="button"
                      className="w-full px-3 py-2 text-left text-sm hover:bg-slate-50"
                      onClick={() => {
                        setKbId(k.id);
                        setMobileKbOpen(false);
                      }}
                    >
                      {k.name}
                    </button>
                  </li>
                ))}
              </ul>
            ) : null}
          </div>
          <span className="hidden text-sm font-semibold text-slate-900 lg:inline">对话与研究</span>
          <button
            type="button"
            onClick={newChat}
            className="ml-auto shrink-0 rounded-full border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50 lg:hidden"
            aria-label="新对话"
          >
            <SquarePen className="h-5 w-5" />
          </button>
        </header>

        {err ? (
          <div className="mx-3 mt-2 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 lg:mx-6">{err}</div>
        ) : null}

        <div className="flex-1 space-y-4 overflow-y-auto px-3 py-4 lg:space-y-6 lg:px-6 lg:py-6">
          {messages.length === 0 && !loading ? (
            <div className="mx-auto max-w-2xl rounded-2xl border border-dashed border-slate-200 bg-white/80 p-6 text-center text-sm text-slate-600">
              <p className="font-medium text-slate-800">开始对话</p>
              <p className="mt-2 text-xs leading-relaxed">
                已接入后端 <code className="rounded bg-slate-100 px-1">POST /api/v1/chat/stream</code>（SSE）与
                EdgeFN 模型流式输出 + Streamdown（Shiki 代码高亮）。请确认服务端已配置{" "}
                <code className="rounded bg-slate-100 px-1">EDGEFN_API_KEY</code> 并重启 API。
              </p>
            </div>
          ) : null}

          {messages.map((m) =>
            m.role === "user" ? (
              <div
                key={m.id}
                className="ml-auto max-w-[90%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-white shadow lg:max-w-3xl lg:rounded-2xl lg:py-3"
              >
                <p className="whitespace-pre-wrap break-words">{m.content}</p>
              </div>
            ) : (
              <div
                key={m.id}
                className="max-w-full rounded-2xl border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-800 shadow-card lg:max-w-4xl lg:p-5"
              >
                <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                  <Sparkles className="h-4 w-4 text-primary" />
                  ScholarMind
                  {m.trace_id ? (
                    <span className="ml-auto font-mono text-[10px] font-normal normal-case text-slate-400">
                      {m.trace_id.slice(0, 8)}…
                    </span>
                  ) : null}
                </div>
                <div className="lg:hidden">
                  <button
                    type="button"
                    onClick={() => setShowThought((v) => !v)}
                    className="mb-2 flex w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-medium text-slate-600"
                  >
                    <span>思维链</span>
                    {showThought ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                  </button>
                  {showThought ? (
                    m.thinkingContent ? (
                      <pre className="mb-3 max-h-48 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-100 bg-slate-50/90 p-3 font-sans text-xs text-slate-600">
                        {m.thinkingContent}
                      </pre>
                    ) : !(m.streamFinal ?? true) ? (
                      <p className="mb-3 text-xs text-slate-500">推理中…</p>
                    ) : (
                      <p className="mb-3 text-xs text-slate-500">
                        本次未返回可见推理字段（与服务商 / 模型实现有关）。
                      </p>
                    )
                  ) : null}
                </div>
                <button
                  type="button"
                  onClick={() => setShowThought((v) => !v)}
                  className="mb-3 hidden w-full items-center justify-between rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-left text-xs font-medium text-slate-600 lg:flex"
                >
                  <span>思维链</span>
                  {showThought ? <ChevronDown className="h-4 w-4" /> : <ChevronRight className="h-4 w-4" />}
                </button>
                {showThought &&
                  (m.thinkingContent ? (
                    <pre className="mb-3 hidden max-h-56 overflow-auto whitespace-pre-wrap break-words rounded-lg border border-slate-100 bg-slate-50/90 p-3 font-sans text-xs text-slate-600 lg:block">
                      {m.thinkingContent}
                    </pre>
                  ) : !(m.streamFinal ?? true) ? (
                    <p className="mb-3 hidden text-xs text-slate-500 lg:block">推理中…</p>
                  ) : (
                    <p className="mb-3 hidden text-xs text-slate-500 lg:block">
                      本次未返回可见推理字段（与服务商 / 模型实现有关）。
                    </p>
                  ))}
                <AssistantMarkdown
                  markdown={m.content}
                  isStreaming={!(m.streamFinal ?? true)}
                />
              </div>
            ),
          )}

          {loading ? (
            <div className="flex items-center gap-2 text-sm text-slate-500">
              <Loader2 className="h-4 w-4 animate-spin text-primary" />
              正在等待回复…
            </div>
          ) : null}

          <div ref={bottomRef} />
        </div>

        <div className="flex flex-wrap gap-2 px-3 pb-1 lg:px-6">
          {["总结要点", "给出参考文献", "列出关键术语"].map((label) => (
            <button
              key={label}
              type="button"
              onClick={() => appendPrompt(label)}
              className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:border-primary/40 hover:text-primary"
            >
              {label}
            </button>
          ))}
        </div>

        <footer className="border-t border-slate-200 bg-white px-2 py-2 lg:p-4">
          <div className="mx-auto max-w-4xl overflow-hidden rounded-[22px] border border-slate-200 bg-white shadow-sm lg:rounded-xl">
            <textarea
              rows={2}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  void handleSend();
                }
              }}
              disabled={loading}
              className="max-h-32 min-h-[40px] w-full resize-none border-0 bg-transparent px-3 pb-2 pt-3 text-[15px] leading-5 text-slate-900 outline-none ring-0 placeholder:text-slate-400 focus:ring-0 disabled:opacity-60 lg:min-h-[72px] lg:px-4 lg:pb-3 lg:pt-3 lg:text-sm"
              placeholder="输入问题…（Enter 发送，Shift+Enter 换行）"
            />
            <div className="flex items-center gap-2 border-t border-slate-100 bg-slate-50/95 px-2 py-2 lg:gap-3 lg:px-3 lg:py-2.5">
              <button
                type="button"
                className="flex h-8 w-8 shrink-0 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 opacity-50"
                aria-label="附件（未接入）"
                disabled
              >
                <Plus className="h-4 w-4" strokeWidth={2.25} />
              </button>
              <div className="scrollbar-none flex min-w-0 flex-1 items-center gap-1 overflow-x-auto [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
                <Toggle label="深度研究" on={deepResearch} onToggle={() => setDeepResearch((v) => !v)} />
                <Toggle label="联网搜索" on={webSearch} onToggle={() => setWebSearch((v) => !v)} />
              </div>
              <button
                type="button"
                disabled={loading || !input.trim()}
                onClick={() => void handleSend()}
                className="inline-flex shrink-0 items-center gap-1.5 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-white shadow-sm transition hover:bg-primary-hover active:scale-[0.98] disabled:opacity-50 lg:rounded-lg lg:px-4 lg:text-sm"
              >
                {loading ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" strokeWidth={2} />}
                发送
              </button>
            </div>
          </div>
        </footer>
      </section>

      <aside className="hidden w-80 shrink-0 flex-col border-l border-slate-200 bg-white xl:flex">
        <div className="border-b border-slate-100 p-4">
          <div className="text-xs font-semibold uppercase tracking-wide text-slate-400">请求追踪</div>
          <div className="mt-1 break-all font-mono text-xs text-slate-600">
            {lastTraceId ?? "—"}
          </div>
          <div className="mt-2 text-xs text-slate-500">与后端 ChatResponse.trace_id 一致</div>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto p-4 text-xs">
          <div className="rounded-lg border border-dashed border-slate-200 p-3 text-slate-500">
            <p className="font-semibold text-slate-700">Agent 步骤</p>
            <p className="mt-1 leading-relaxed">
              正文已通过 SSE 流式渲染；此处可后续接入计划、检索、工具调用等元事件。
            </p>
          </div>
        </div>
        <div className="border-t border-slate-100 p-4">
          <div className="text-xs font-semibold text-slate-500">当前知识库</div>
          <div className="mt-1 text-sm font-medium text-slate-900">{kbName}</div>
        </div>
      </aside>
    </div>
  );
}

function Toggle({
  label,
  on,
  onToggle,
}: {
  label: string;
  on: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      className={
        on
          ? "shrink-0 rounded-full bg-primary-soft px-2.5 py-1 text-xs font-medium text-primary sm:px-3"
          : "shrink-0 rounded-full bg-white px-2.5 py-1 text-xs font-medium text-slate-500 ring-1 ring-slate-200 sm:px-3"
      }
    >
      {label}
    </button>
  );
}
