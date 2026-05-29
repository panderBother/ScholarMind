import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Bot, Loader2, Send, Sparkles } from "lucide-react";
import { AssistantMarkdown } from "@/components/AssistantMarkdown";
import { ChatRagSources } from "@/components/ChatRagSources";
import type { RagSourceDto } from "@/services/chat";
import { getExpert, streamExpertChat, type ExpertDto } from "@/services/experts";
import { mergeThinkingParts, partitionThinkingBlocks } from "@/utils/partitionThinking";

type Msg = {
  id: string;
  role: "user" | "assistant";
  content: string;
  thinkingContent?: string;
  streamFinal?: boolean;
  ragSources?: RagSourceDto[];
};

export function ExpertChatPage() {
  const { expertId } = useParams<{ expertId: string }>();
  const nav = useNavigate();
  const bottomRef = useRef<HTMLDivElement>(null);
  const [expert, setExpert] = useState<ExpertDto | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [hydrating, setHydrating] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [deepResearch, setDeepResearch] = useState(false);

  useEffect(() => {
    if (!expertId) return;
    setHydrating(true);
    getExpert(expertId)
      .then(setExpert)
      .catch((e) => setErr(e instanceof Error ? e.message : "加载失败"))
      .finally(() => setHydrating(false));
  }, [expertId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const handleSend = useCallback(async () => {
    const text = input.trim();
    if (!text || !expertId || loading) return;
    setInput("");
    setErr(null);
    const assistantId = crypto.randomUUID();
    setMessages((m) => [
      ...m,
      { id: crypto.randomUUID(), role: "user", content: text },
      { id: assistantId, role: "assistant", content: "", streamFinal: false },
    ]);
    setLoading(true);
    let acc = "";
    let thinkingAcc = "";
    try {
      await streamExpertChat(
        expertId,
        { message: text, deep_research: deepResearch, conversation_id: conversationId },
        {
          onTraceId: () => undefined,
          onConversationId: (cid) => setConversationId(cid),
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
          onRagSources: (_kbId, sources) => {
            setMessages((m) =>
              m.map((row) => (row.id === assistantId ? { ...row, ragSources: sources } : row)),
            );
          },
          onError: (msg) => setErr(msg),
          onDone: () => {
            setMessages((m) =>
              m.map((row) => (row.id === assistantId ? { ...row, streamFinal: true } : row)),
            );
          },
        },
      );
    } catch (e) {
      setErr(e instanceof Error ? e.message : "发送失败");
    } finally {
      setLoading(false);
    }
  }, [conversationId, deepResearch, expertId, input, loading]);

  if (hydrating) {
    return (
      <div className="flex flex-1 items-center justify-center gap-2 text-sm text-slate-500">
        <Loader2 className="h-5 w-5 animate-spin text-primary" />
        加载专家…
      </div>
    );
  }

  if (!expert) {
    return (
      <div className="flex flex-1 flex-col items-center justify-center gap-3 p-6 text-sm text-slate-600">
        <p>{err ?? "专家不存在"}</p>
        <button type="button" onClick={() => nav("/experts")} className="text-primary underline">
          返回列表
        </button>
      </div>
    );
  }

  return (
    <section className="flex min-h-0 flex-1 flex-col">
      <header className="flex shrink-0 items-center gap-3 border-b border-slate-200 bg-white px-4 py-3 lg:px-6">
        <button
          type="button"
          onClick={() => nav("/experts")}
          className="rounded-lg p-1.5 text-slate-600 hover:bg-slate-100"
          aria-label="返回"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-violet-100 text-violet-700">
          <Bot className="h-5 w-5" />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-sm font-semibold text-slate-900">{expert.name}</h1>
          <p className="truncate text-[11px] text-slate-500">{expert.description ?? "领域专家对话"}</p>
        </div>
        <label className="flex items-center gap-1.5 text-xs text-slate-600">
          <input
            type="checkbox"
            checked={deepResearch}
            onChange={(e) => setDeepResearch(e.target.checked)}
            className="rounded border-slate-300"
          />
          深度研究
        </label>
      </header>

      {err ? (
        <div className="mx-4 mt-2 rounded-lg bg-red-50 px-3 py-2 text-xs text-red-700 lg:mx-6">{err}</div>
      ) : null}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-4 py-4 lg:px-6">
        {messages.length === 0 ? (
          <div className="mx-auto max-w-2xl rounded-2xl border border-dashed border-violet-200 bg-violet-50/50 p-6 text-center text-sm text-slate-600">
            <p className="font-medium text-slate-800">向 {expert.name} 提问</p>
            <p className="mt-2 text-xs leading-relaxed">
              回答将结合知识库 RAG 检索与专家人设；多轮对话会自动记住上下文。
            </p>
          </div>
        ) : null}

        {messages.map((m) =>
          m.role === "user" ? (
            <div
              key={m.id}
              className="ml-auto max-w-[90%] rounded-2xl rounded-br-md bg-primary px-4 py-2.5 text-sm text-white lg:max-w-3xl"
            >
              {m.content}
            </div>
          ) : (
            <div
              key={m.id}
              className="max-w-full rounded-2xl border border-slate-200 bg-white p-4 shadow-card lg:max-w-4xl"
            >
              <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-slate-400">
                <Sparkles className="h-4 w-4 text-violet-600" />
                {expert.name}
              </div>
              {m.ragSources && m.ragSources.length > 0 ? (
                <ChatRagSources kbId={expert.kb_id} sources={m.ragSources} />
              ) : null}
              {m.thinkingContent ? (
                <pre className="mb-3 max-h-40 overflow-auto whitespace-pre-wrap rounded-lg border border-slate-100 bg-slate-50 p-3 text-xs text-slate-600">
                  {m.thinkingContent}
                </pre>
              ) : null}
              <AssistantMarkdown markdown={m.content} isStreaming={!(m.streamFinal ?? true)} />
            </div>
          ),
        )}
        {loading ? (
          <div className="flex items-center gap-2 text-sm text-slate-500">
            <Loader2 className="h-4 w-4 animate-spin" /> 专家思考中…
          </div>
        ) : null}
        <div ref={bottomRef} />
      </div>

      <footer className="shrink-0 border-t border-slate-200 bg-white p-3 lg:p-4">
        <div className="mx-auto flex max-w-4xl gap-2">
          <textarea
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                void handleSend();
              }
            }}
            rows={2}
            placeholder="输入问题…"
            className="min-h-[44px] flex-1 resize-none rounded-xl border border-slate-200 px-3 py-2 text-sm outline-none focus:border-primary"
          />
          <button
            type="button"
            disabled={loading || !input.trim()}
            onClick={() => void handleSend()}
            className="inline-flex h-11 items-center gap-1 rounded-xl bg-primary px-4 text-sm font-semibold text-white disabled:opacity-50"
          >
            <Send className="h-4 w-4" />
            发送
          </button>
        </div>
      </footer>
    </section>
  );
}
