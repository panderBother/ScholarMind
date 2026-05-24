import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ImperativePanelHandle } from "react-resizable-panels";
import { Panel, PanelGroup, PanelResizeHandle } from "react-resizable-panels";
import { useNavigate } from "react-router-dom";
import {
  BookOpen,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ExternalLink,
  GripVertical,
  Loader2,
  MessageSquare,
  Pencil,
  Plus,
  Send,
  Sparkles,
  SquarePen,
  Trash2,
} from "lucide-react";
import { AssistantMarkdown } from "@/components/AssistantMarkdown";
import { useUi } from "@/components/ui/UiProvider";
import { getAccessToken } from "@/services/auth";
import { streamChatMessage, type ChatToolResult } from "@/services/chat";
import {
  type ConversationDto,
  fetchConversation,
  fetchConversationMessages,
  getStoredConversationId,
  listConversations,
  deleteConversation,
  updateConversationTitle,
  setStoredConversationId,
} from "@/services/conversations";
import {
  setBuiltinMcpEnabled,
} from "@/services/mcpTools";
import { listKnowledgeBases, type KnowledgeBaseDto } from "@/services/knowledgeBases";
import {
  extractConversationKnowledge,
  importKnowledgeDrafts,
  submitChatFeedback,
} from "@/services/distill";
import { generateReportFromConversation } from "@/services/reports";
import { mergeThinkingParts, partitionThinkingBlocks } from "@/utils/partitionThinking";

type FileToolLog = {
  tool: string;
  ok: boolean;
  summary: string;
};

type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  trace_id?: string;
  streamFinal?: boolean;
  thinkingContent?: string;
  fileToolLogs?: FileToolLog[];
};

function summarizeToolResult(payload: ChatToolResult): string {
  const r = payload.result;
  if (!payload.ok && typeof r.error === "string") return r.error;
  if (typeof r.path === "string") {
    const extra =
      payload.tool.startsWith("write") && typeof r.bytes_written === "number"
        ? `（${r.bytes_written} 字节）`
        : payload.tool === "read_document" && r.truncated
          ? "（内容已截断）"
          : "";
    return `${r.path}${extra}`;
  }
  if (Array.isArray(r.allowed_roots)) {
    return (r.allowed_roots as string[]).slice(0, 3).join("；") + ((r.allowed_roots as string[]).length > 3 ? "…" : "");
  }
  return payload.ok ? "完成" : "失败";
}

type LeftRailTab = "sessions" | "knowledge";

function formatConversationLabel(c: ConversationDto): string {
  if (c.title && c.title.trim()) return c.title.trim();
  try {
    const d = new Date(c.updated_at);
    return `会话 ${d.toLocaleString(undefined, { month: "numeric", day: "numeric", hour: "2-digit", minute: "2-digit" })}`;
  } catch {
    return `会话 ${c.id.slice(0, 8)}`;
  }
}

/**
 * 智能对话：SSE + 多轮会话（刷新后从后端恢复）；桌面端三栏可拖拽宽度、侧栏可折叠。
 */
export function ChatPage() {
  const nav = useNavigate();
  const { confirm, prompt, message } = useUi();
  const bottomRef = useRef<HTMLDivElement>(null);
  const leftPanelRef = useRef<ImperativePanelHandle>(null);
  const rightPanelRef = useRef<ImperativePanelHandle>(null);

  const [kbs, setKbs] = useState<KnowledgeBaseDto[]>([]);
  const [kbId, setKbId] = useState<string>("");
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [deepResearch, setDeepResearch] = useState(true);
  const [webSearch, setWebSearch] = useState(false);
  const [fileTools, setFileTools] = useState(false);
  const [loading, setLoading] = useState(false);
  const [err, setErr] = useState<string | null>(null);
  const [showThought, setShowThought] = useState(true);
  const [mobileKbOpen, setMobileKbOpen] = useState(false);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [hydrating, setHydrating] = useState(() => !!(getAccessToken() && getStoredConversationId()));
  const [leftCollapsed, setLeftCollapsed] = useState(false);
  const [rightCollapsed, setRightCollapsed] = useState(false);
  const [conversations, setConversations] = useState<ConversationDto[]>([]);
  const [loadingConvList, setLoadingConvList] = useState(false);
  const [switchingConv, setSwitchingConv] = useState(false);
  const [mobileSessionsOpen, setMobileSessionsOpen] = useState(false);
  /** 桌面左侧栏：会话与知识库分栏，避免混在同一滚动区 */
  const [leftRailTab, setLeftRailTab] = useState<LeftRailTab>("sessions");
  const lastUserQueryRef = useRef("");
  const [extracting, setExtracting] = useState(false);
  const [generatingReport, setGeneratingReport] = useState(false);

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

  const loadConversationList = useCallback(async () => {
    if (!getAccessToken()) return;
    setLoadingConvList(true);
    try {
      const rows = await listConversations(80);
      setConversations(rows);
    } catch {
      /* 列表失败不阻断对话 */
    } finally {
      setLoadingConvList(false);
    }
  }, []);

  useEffect(() => {
    if (getAccessToken()) void loadConversationList();
  }, [loadConversationList]);

  const applyConversationPayload = useCallback((conv: ConversationDto, msgs: Awaited<ReturnType<typeof fetchConversationMessages>>) => {
    setConversationId(conv.id);
    setStoredConversationId(conv.id);
    if (conv.knowledge_base_id) setKbId(conv.knowledge_base_id);
    setDeepResearch(conv.deep_research);
    setWebSearch(conv.web_search);
    setMessages(
      msgs.map((m) => ({
        id: m.id,
        role: m.role === "assistant" ? "assistant" : "user",
        content: m.content,
        trace_id: m.trace_id ?? undefined,
        streamFinal: true,
      })),
    );
  }, []);

  /** 刷新后：从 localStorage 的会话 id 拉取消息（后端已持久化） */
  useEffect(() => {
    if (!getAccessToken()) {
      setHydrating(false);
      return;
    }
    const cid = getStoredConversationId();
    if (!cid) {
      setHydrating(false);
      return;
    }
    let cancelled = false;
    void (async () => {
      try {
        const [conv, msgs] = await Promise.all([fetchConversation(cid), fetchConversationMessages(cid)]);
        if (cancelled) return;
        applyConversationPayload(conv, msgs);
        void loadConversationList();
      } catch {
        setStoredConversationId(null);
        setConversationId(null);
      } finally {
        if (!cancelled) setHydrating(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [applyConversationPayload, loadConversationList]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  const selectConversation = useCallback(
    async (id: string) => {
      if (loading || switchingConv) return;
      if (id === conversationId) return;
      setSwitchingConv(true);
      setErr(null);
      setMobileSessionsOpen(false);
      try {
        const [conv, msgs] = await Promise.all([fetchConversation(id), fetchConversationMessages(id)]);
        applyConversationPayload(conv, msgs);
        void loadConversationList();
      } catch {
        setErr("加载会话失败，可能已被删除");
        setStoredConversationId(null);
        setConversationId(null);
        setMessages([]);
      } finally {
        setSwitchingConv(false);
      }
    },
    [applyConversationPayload, conversationId, loadConversationList, loading, switchingConv],
  );

  const handleFeedback = async () => {
    const correction = await prompt({
      title: "纠错反馈",
      message: "请填写您认为更正确的答案或补充说明：",
      multiline: true,
      placeholder: "输入纠正内容…",
      confirmText: "提交",
    });
    if (!correction?.trim()) return;
    try {
      await submitChatFeedback({
        knowledge_base_id: kbId || null,
        conversation_id: conversationId,
        query_text: lastUserQueryRef.current || null,
        correction: correction.trim(),
      });
      message.success("感谢反馈，已记录用于知识蒸馏分析。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "提交反馈失败");
    }
  };

  const handleExtractToKb = async () => {
    if (!conversationId || !kbId) {
      setErr("请先选择知识库并至少进行一轮对话");
      return;
    }
    setExtracting(true);
    setErr(null);
    try {
      const { drafts } = await extractConversationKnowledge(conversationId, { kb_id: kbId });
      const preview = drafts.map((d, i) => `${i + 1}. ${d.title}`).join("\n");
      const ok = await confirm({
        title: "导入知识条目",
        message: `提炼出 ${drafts.length} 条草稿：\n${preview}\n\n确认导入为知识条目（草稿）？`,
        confirmText: "导入",
        type: "info",
      });
      if (!ok) return;
      await importKnowledgeDrafts(kbId, drafts, false);
      message.success("已导入为草稿条目，可在「文档管理 → 条目视图」中发布。");
    } catch (e) {
      setErr(e instanceof Error ? e.message : "提炼失败");
    } finally {
      setExtracting(false);
    }
  };

  const handleGenerateReport = async () => {
    if (!conversationId || !kbId) {
      setErr("请先选择知识库并至少进行一轮对话");
      return;
    }
    setGeneratingReport(true);
    setErr(null);
    try {
      const report = await generateReportFromConversation(conversationId, { kb_id: kbId });
      message.success("报告已生成");
      nav(`/reports/${report.id}`);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "生成报告失败");
    } finally {
      setGeneratingReport(false);
    }
  };

  const handleSend = async () => {
    const text = input.trim();
    if (!text || loading || hydrating || switchingConv) return;
    setErr(null);
    lastUserQueryRef.current = text;
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
          file_tools: fileTools,
          conversation_id: conversationId,
        },
        {
          onTraceId: (traceId) => {
            setMessages((m) =>
              m.map((row) => (row.id === assistantId ? { ...row, trace_id: traceId } : row)),
            );
          },
          onConversationId: (cid) => {
            setConversationId(cid);
            setStoredConversationId(cid);
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
          onToolResult: (payload) => {
            if (!payload.ok) return;
            const log: FileToolLog = {
              tool: payload.tool,
              ok: payload.ok,
              summary: summarizeToolResult(payload),
            };
            setMessages((m) =>
              m.map((row) =>
                row.id === assistantId
                  ? { ...row, fileToolLogs: [...(row.fileToolLogs ?? []), log] }
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
          row.id === assistantId ? { ...row, content: mdBody, streamFinal: true } : row,
        ),
      );
    } finally {
      setLoading(false);
      void loadConversationList();
    }
  };

  const newChat = () => {
    setMessages([]);
    setErr(null);
    setInput("");
    setConversationId(null);
    setStoredConversationId(null);
    void loadConversationList();
  };

  const handleRenameConversation = useCallback(
    async (c: ConversationDto) => {
      const next = await prompt({
        title: "修改会话标题",
        defaultValue: c.title?.trim() || "",
        placeholder: "输入会话标题",
        validate: (value) => (value.trim() ? null : "标题不能为空"),
      });
      if (next === null) return;
      const title = next.trim();
      if (title === (c.title?.trim() || "")) return;
      try {
        const updated = await updateConversationTitle(c.id, title);
        setConversations((rows) => rows.map((row) => (row.id === updated.id ? updated : row)));
        message.success("标题已更新");
      } catch (e) {
        const msg = e instanceof Error ? e.message : "修改标题失败";
        setErr(msg);
        message.error(msg);
      }
    },
    [message, prompt],
  );

  const handleDeleteConversation = useCallback(
    async (c: ConversationDto) => {
      const label = formatConversationLabel(c);
      const ok = await confirm({
        title: "删除会话",
        message: `确定删除「${label}」？\n对话记录将无法恢复。`,
        confirmText: "删除",
        cancelText: "取消",
        type: "danger",
      });
      if (!ok) return;
      try {
        await deleteConversation(c.id);
        setConversations((rows) => rows.filter((row) => row.id !== c.id));
        if (c.id === conversationId) {
          newChat();
        }
        message.success("会话已删除");
      } catch (e) {
        const msg = e instanceof Error ? e.message : "删除失败";
        setErr(msg);
        message.error(msg);
      }
    },
    [confirm, conversationId, message],
  );

  const appendPrompt = (t: string) => {
    setInput((prev) => (prev ? `${prev}\n${t}` : t));
  };

  const knowledgeGraphPlaceholder = (
    <div className="border-t border-slate-100 p-3">
      <div className="mb-2 text-xs font-semibold text-slate-500">知识图谱（示意）</div>
      <div className="relative h-36 rounded-lg bg-slate-50 p-2 text-[10px] text-slate-500">
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
  );

  const leftAside = (
    <aside className="flex h-full min-h-0 flex-col border-slate-200 bg-white lg:border-r">
      <div className="flex shrink-0 items-center gap-1 border-b border-slate-100 p-2">
        {!leftCollapsed ? (
          <>
            <span className="min-w-0 flex-1 truncate px-1 text-xs font-semibold text-slate-600">
              {leftRailTab === "sessions" ? "历史会话" : "检索范围"}
            </span>
            <button
              type="button"
              onClick={() => leftPanelRef.current?.collapse()}
              className="shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-slate-100 hover:text-slate-800"
              title="收起侧栏"
              aria-label="收起左侧栏"
            >
              <ChevronLeft className="h-4 w-4" />
            </button>
          </>
        ) : (
          <button
            type="button"
            onClick={() => leftPanelRef.current?.expand()}
            className="mx-auto rounded-md p-1.5 text-slate-500 hover:bg-slate-100"
            title="展开侧栏"
            aria-label="展开左侧栏"
          >
            <ChevronRight className="h-4 w-4" />
          </button>
        )}
        {!leftCollapsed ? (
          <button
            type="button"
            onClick={newChat}
            className="shrink-0 whitespace-nowrap rounded-md px-2 py-1 text-xs font-medium text-primary hover:bg-primary-soft"
          >
            新对话
          </button>
        ) : null}
      </div>
      {!leftCollapsed ? (
        <>
          <div className="shrink-0 border-b border-slate-100 px-2 pb-2 pt-2">
            <div
              className="flex rounded-lg bg-slate-100 p-0.5"
              role="tablist"
              aria-label="侧栏分区"
            >
              <button
                type="button"
                role="tab"
                aria-selected={leftRailTab === "sessions"}
                onClick={() => setLeftRailTab("sessions")}
                className={
                  leftRailTab === "sessions"
                    ? "flex flex-1 items-center justify-center gap-1 rounded-md bg-white px-2 py-1.5 text-xs font-semibold text-slate-900 shadow-sm"
                    : "flex flex-1 items-center justify-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
                }
              >
                <MessageSquare className="h-3.5 w-3.5" aria-hidden />
                会话
              </button>
              <button
                type="button"
                role="tab"
                aria-selected={leftRailTab === "knowledge"}
                onClick={() => setLeftRailTab("knowledge")}
                className={
                  leftRailTab === "knowledge"
                    ? "flex flex-1 items-center justify-center gap-1 rounded-md bg-white px-2 py-1.5 text-xs font-semibold text-slate-900 shadow-sm"
                    : "flex flex-1 items-center justify-center gap-1 rounded-md px-2 py-1.5 text-xs font-medium text-slate-600 hover:text-slate-900"
                }
              >
                <BookOpen className="h-3.5 w-3.5" aria-hidden />
                知识库
              </button>
            </div>
          </div>

          <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
            {leftRailTab === "sessions" ? (
              <div className="flex min-h-0 flex-1 flex-col">
                <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain px-2 pb-2 pt-1">
                  <div className="mb-2 flex items-center justify-between px-1">
                    <span className="text-[11px] font-semibold uppercase tracking-wide text-slate-400">
                      对话列表
                    </span>
                    {loadingConvList ? (
                      <Loader2 className="h-3 w-3 animate-spin text-slate-400" aria-hidden />
                    ) : null}
                  </div>
                  <button
                    type="button"
                    onClick={newChat}
                    disabled={switchingConv}
                    className={
                      !conversationId
                        ? "mb-2 flex w-full items-center gap-2 rounded-lg bg-primary-soft px-2 py-2 text-left text-xs font-medium text-primary"
                        : "mb-2 flex w-full items-center gap-2 rounded-lg px-2 py-2 text-left text-xs text-slate-600 ring-1 ring-slate-100 hover:bg-slate-50"
                    }
                  >
                    <SquarePen className="h-3.5 w-3.5 shrink-0" />
                    <span className="truncate">新草稿（尚未入库）</span>
                  </button>
                  <ul className="space-y-1">
                    {conversations.map((c) => (
                      <ConversationRow
                        key={c.id}
                        conversation={c}
                        active={c.id === conversationId}
                        disabled={switchingConv}
                        variant="desktop"
                        onSelect={() => void selectConversation(c.id)}
                        onRename={() => void handleRenameConversation(c)}
                        onDelete={() => void handleDeleteConversation(c)}
                      />
                    ))}
                  </ul>
                  {!loadingConvList && conversations.length === 0 ? (
                    <p className="px-1 py-3 text-[11px] leading-relaxed text-slate-500">
                      暂无历史会话。发送第一条消息后，会话会保存并出现在此列表。
                    </p>
                  ) : null}
                </div>
                <div className="shrink-0 border-t border-slate-100 bg-slate-50/90 px-2 py-2">
                  <p className="mb-1.5 px-1 text-[10px] font-semibold uppercase tracking-wide text-slate-400">
                    当前检索知识库
                  </p>
                  <button
                    type="button"
                    onClick={() => setLeftRailTab("knowledge")}
                    className="flex w-full items-center gap-2 rounded-lg border border-slate-200 bg-white px-2 py-2 text-left text-xs text-slate-800 shadow-sm hover:border-primary/30 hover:bg-primary-soft/40"
                  >
                    <BookOpen className="h-4 w-4 shrink-0 text-primary" aria-hidden />
                    <span className="min-w-0 flex-1 truncate font-medium">{kbName}</span>
                    <span className="shrink-0 text-[10px] text-primary">切换</span>
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex min-h-0 flex-1 flex-col overflow-hidden">
                <div className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
                  <div className="flex items-start justify-between gap-2 px-2 pb-2 pt-1">
                    <p className="text-[11px] leading-relaxed text-slate-500">
                      选择后，新消息将关联该知识库检索（已开始的会话仍沿用当时设置）。
                    </p>
                    <button
                      type="button"
                      onClick={() => nav("/knowledge-bases")}
                      className="inline-flex shrink-0 items-center gap-0.5 rounded-md px-1.5 py-1 text-[10px] font-medium text-primary hover:bg-primary-soft"
                    >
                      管理
                      <ExternalLink className="h-3 w-3" aria-hidden />
                    </button>
                  </div>
                  <ul className="space-y-1 px-2 pb-2 text-sm">
                    {kbs.length === 0 ? (
                      <li className="rounded-lg border border-dashed border-slate-200 px-3 py-4 text-center text-xs text-slate-500">
                        暂无知识库。
                        <button
                          type="button"
                          onClick={() => nav("/knowledge-bases")}
                          className="mt-2 block w-full rounded-lg bg-primary px-3 py-2 font-semibold text-white hover:bg-primary-hover"
                        >
                          去创建
                        </button>
                      </li>
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
                  {knowledgeGraphPlaceholder}
                </div>
              </div>
            )}
          </div>
        </>
      ) : null}
    </aside>
  );

  const rightAside = (
    <aside className="flex h-full min-h-0 flex-col border-slate-200 bg-white lg:border-l">
      <div className="flex items-center gap-1 border-b border-slate-100 p-2">
        {!rightCollapsed ? (
          <>
            <button
              type="button"
              onClick={() => rightPanelRef.current?.collapse()}
              className="shrink-0 rounded-md p-1.5 text-slate-500 hover:bg-slate-100"
              title="收起追踪栏"
              aria-label="收起请求追踪侧栏"
            >
              <ChevronRight className="h-4 w-4" />
            </button>
            <span className="min-w-0 flex-1 truncate text-xs font-semibold uppercase tracking-wide text-slate-400">
              请求追踪
            </span>
          </>
        ) : (
          <button
            type="button"
            onClick={() => rightPanelRef.current?.expand()}
            className="mx-auto rounded-md p-1.5 text-slate-500 hover:bg-slate-100"
            title="展开追踪"
            aria-label="展开请求追踪侧栏"
          >
            <ChevronLeft className="h-4 w-4" />
          </button>
        )}
      </div>
      {!rightCollapsed ? (
        <>
          <div className="border-b border-slate-100 p-4">
            <div className="break-all font-mono text-xs text-slate-600">{lastTraceId ?? "—"}</div>
            <div className="mt-2 text-xs text-slate-500">与后端 ChatResponse.trace_id 一致</div>
          </div>
          <div className="min-h-0 flex-1 space-y-3 overflow-y-auto p-4 text-xs">
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
        </>
      ) : null}
    </aside>
  );

  const mainSection = (
    <section className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden bg-slate-50">
      <header className="flex shrink-0 items-center gap-2 border-b border-slate-200 bg-white px-3 py-2.5 lg:px-6 lg:py-3">
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
        <button
          type="button"
          onClick={() => {
            setMobileSessionsOpen((v) => !v);
            setMobileKbOpen(false);
          }}
          className="shrink-0 rounded-xl border border-slate-200 bg-white p-2 text-slate-600 hover:bg-slate-50 lg:hidden"
          aria-expanded={mobileSessionsOpen}
          aria-label="会话列表"
        >
          <MessageSquare className="h-5 w-5" />
        </button>
        <span className="hidden text-sm font-semibold text-slate-900 lg:inline">智能对话</span>
        <button
          type="button"
          onClick={newChat}
          className="ml-auto shrink-0 rounded-full border border-slate-200 bg-white p-2 text-slate-500 hover:bg-slate-50 lg:hidden"
          aria-label="新对话"
        >
          <SquarePen className="h-5 w-5" />
        </button>
      </header>

      {mobileSessionsOpen ? (
        <div className="max-h-[40vh] shrink-0 overflow-y-auto overscroll-contain border-b border-slate-200 bg-white px-3 py-2 lg:hidden">
          <div className="mb-2 flex items-center justify-between text-xs font-semibold text-slate-500">
            <span>会话</span>
            {loadingConvList ? <Loader2 className="h-3.5 w-3.5 animate-spin text-slate-400" aria-hidden /> : null}
          </div>
          <button
            type="button"
            onClick={newChat}
            disabled={switchingConv}
            className={
              !conversationId
                ? "mb-1 flex w-full items-center gap-2 rounded-lg bg-primary-soft px-3 py-2.5 text-left text-sm font-medium text-primary"
                : "mb-1 flex w-full items-center gap-2 rounded-lg px-3 py-2.5 text-left text-sm text-slate-700 hover:bg-slate-50"
            }
          >
            <SquarePen className="h-4 w-4 shrink-0" />
            新草稿
          </button>
          <ul className="space-y-1 pb-2">
            {conversations.map((c) => (
              <ConversationRow
                key={c.id}
                conversation={c}
                active={c.id === conversationId}
                disabled={switchingConv}
                variant="mobile"
                onSelect={() => void selectConversation(c.id)}
                onRename={() => void handleRenameConversation(c)}
                onDelete={() => void handleDeleteConversation(c)}
              />
            ))}
          </ul>
        </div>
      ) : null}

      {err ? (
        <div className="mx-3 mt-2 shrink-0 rounded-lg bg-red-50 px-3 py-2 text-sm text-red-700 lg:mx-6">{err}</div>
      ) : null}

      <div className="min-h-0 flex-1 space-y-4 overflow-y-auto overscroll-contain px-3 py-4 lg:space-y-6 lg:px-6 lg:py-6">
        {hydrating && messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-3 py-16 text-sm text-slate-500">
            <Loader2 className="h-8 w-8 animate-spin text-primary" />
            <p>正在从服务器恢复上次会话…</p>
          </div>
        ) : null}

        {!hydrating && messages.length === 0 && !loading ? (
          <div className="mx-auto max-w-2xl rounded-2xl border border-dashed border-slate-200 bg-white/80 p-6 text-center text-sm text-slate-600">
            <p className="font-medium text-slate-800">开始对话</p>
            <p className="mt-2 text-xs leading-relaxed">
              多轮对话会保存到服务器；刷新页面会自动恢复当前会话。点击「新对话」可清空并开始新会话。
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
                KnowMind
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
              {(m.fileToolLogs ?? []).some((log) => log.ok) ? (
                <ul className="mb-3 space-y-1.5 rounded-lg border border-emerald-100 bg-emerald-50/80 px-3 py-2 text-xs text-emerald-900">
                  {(m.fileToolLogs ?? [])
                    .filter((log) => log.ok)
                    .map((log, i) => (
                      <li key={`${log.tool}-${i}`} className="break-all">
                        <span className="font-medium">{log.tool}</span>
                        <span className="text-emerald-700"> · </span>
                        {log.summary}
                      </li>
                    ))}
                </ul>
              ) : null}
              <AssistantMarkdown markdown={m.content} isStreaming={!(m.streamFinal ?? true)} />
              {(m.streamFinal ?? true) && m.content ? (
                <div className="mt-3 flex flex-wrap gap-2 border-t border-slate-100 pt-2">
                  <button
                    type="button"
                    onClick={() => void handleFeedback()}
                    className="text-xs font-medium text-slate-500 hover:text-red-600"
                  >
                    不满意 / 纠错
                  </button>
                </div>
              ) : null}
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

      <div className="flex shrink-0 flex-wrap gap-2 px-3 pb-1 lg:px-6">
        {["总结要点", "列出引用来源", "列出关键术语"].map((label) => (
          <button
            key={label}
            type="button"
            onClick={() => appendPrompt(label)}
            className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700 shadow-sm hover:border-primary/40 hover:text-primary"
          >
            {label}
          </button>
        ))}
        <button
          type="button"
          disabled={!conversationId || !kbId || extracting}
          onClick={() => void handleExtractToKb()}
          className="rounded-full border border-violet-200 bg-violet-50 px-3 py-1.5 text-xs font-medium text-violet-800 shadow-sm hover:bg-violet-100 disabled:opacity-50"
        >
          {extracting ? "提炼中…" : "提炼到知识库"}
        </button>
        <button
          type="button"
          disabled={!conversationId || !kbId || generatingReport || loading}
          onClick={() => void handleGenerateReport()}
          className="rounded-full border border-primary/30 bg-primary/5 px-3 py-1.5 text-xs font-medium text-primary shadow-sm hover:bg-primary/10 disabled:opacity-50"
        >
          {generatingReport ? "生成报告中…" : "生成报告"}
        </button>
      </div>

      <footer className="shrink-0 border-t border-slate-200 bg-white px-2 py-2 lg:p-4">
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
            disabled={loading || hydrating || switchingConv}
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
              <Toggle
                label="联网搜索"
                on={webSearch}
                onToggle={() => {
                  const next = !webSearch;
                  setWebSearch(next);
                  void setBuiltinMcpEnabled("web_search", next).catch(() => undefined);
                }}
              />
              <Toggle
                label="文件读写"
                on={fileTools}
                onToggle={() => {
                  const next = !fileTools;
                  setFileTools(next);
                  void setBuiltinMcpEnabled("file_writer", next).catch(() => undefined);
                }}
              />
            </div>
            <button
              type="button"
              disabled={loading || hydrating || switchingConv || !input.trim()}
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
  );

  const resizeHandleClass =
    "group relative flex w-2 shrink-0 items-center justify-center bg-slate-100 hover:bg-primary/15 data-[panel-resize-handle-active]:bg-primary/25 outline-none";

  return (
    <div className="flex min-h-0 flex-1 flex-col overflow-hidden lg:min-h-0 lg:flex-row">
      {/* 移动端：单栏主内容 */}
      <div className="flex min-h-0 min-w-0 flex-1 flex-col overflow-hidden lg:hidden">{mainSection}</div>

      {/* 桌面端：可拖拽 + 可折叠侧栏；Panel 必须是纵向 flex 容器，子项 flex-1 + overflow 才能正确滚动 */}
      <div className="hidden min-h-0 min-w-0 flex-1 overflow-hidden lg:flex lg:h-full lg:min-h-0 lg:flex-col">
        <PanelGroup
          direction="horizontal"
          autoSaveId="knowmind-chat-layout"
          className="flex h-full min-h-0 w-full flex-1"
        >
          <Panel
            ref={leftPanelRef}
            collapsible
            collapsedSize={4}
            defaultSize={22}
            minSize={14}
            maxSize={36}
            className="flex min-h-0 min-w-0 flex-col"
            onCollapse={() => setLeftCollapsed(true)}
            onExpand={() => setLeftCollapsed(false)}
          >
            {leftAside}
          </Panel>
          <PanelResizeHandle className={resizeHandleClass}>
            <GripVertical className="h-5 w-5 text-slate-400 opacity-60 group-hover:opacity-100" aria-hidden />
          </PanelResizeHandle>
          <Panel defaultSize={56} minSize={38} className="flex min-h-0 min-w-0 flex-col overflow-hidden">
            {mainSection}
          </Panel>
          <PanelResizeHandle className={resizeHandleClass}>
            <GripVertical className="h-5 w-5 text-slate-400 opacity-60 group-hover:opacity-100" aria-hidden />
          </PanelResizeHandle>
          <Panel
            ref={rightPanelRef}
            collapsible
            collapsedSize={4}
            defaultSize={22}
            minSize={14}
            maxSize={34}
            className="flex min-h-0 min-w-0 flex-col"
            onCollapse={() => setRightCollapsed(true)}
            onExpand={() => setRightCollapsed(false)}
          >
            {rightAside}
          </Panel>
        </PanelGroup>
      </div>
    </div>
  );
}

function ConversationRow({
  conversation,
  active,
  disabled,
  variant,
  onSelect,
  onRename,
  onDelete,
}: {
  conversation: ConversationDto;
  active: boolean;
  disabled: boolean;
  variant: "desktop" | "mobile";
  onSelect: () => void;
  onRename: () => void;
  onDelete: () => void;
}) {
  const label = formatConversationLabel(conversation);
  const isDesktop = variant === "desktop";
  const rowClass = active
    ? isDesktop
      ? "bg-primary-soft text-primary"
      : "bg-primary-soft text-primary"
    : isDesktop
      ? "text-slate-700 hover:bg-slate-50"
      : "text-slate-800 hover:bg-slate-50";
  const textClass = isDesktop ? "text-xs" : "text-sm";
  const padClass = isDesktop ? "px-2 py-2" : "px-3 py-2.5";

  return (
    <li className="group relative">
      <div
        className={`flex items-start gap-1 rounded-lg ${padClass} ${rowClass} ${active ? "font-medium" : ""}`}
      >
        <button
          type="button"
          disabled={disabled}
          onClick={onSelect}
          className={`min-w-0 flex-1 text-left ${textClass}`}
        >
          <span className="line-clamp-2">{label}</span>
        </button>
        <ConversationActions
          disabled={disabled}
          onRename={onRename}
          onDelete={onDelete}
          compact={isDesktop}
        />
      </div>
    </li>
  );
}

function ConversationActions({
  disabled,
  onRename,
  onDelete,
  compact,
}: {
  disabled: boolean;
  onRename: () => void;
  onDelete: () => void;
  compact: boolean;
}) {
  const btnClass = compact
    ? "rounded p-1 text-slate-400 hover:bg-white/80 hover:text-slate-700"
    : "rounded-md p-1.5 text-slate-400 hover:bg-slate-100 hover:text-slate-700";
  const iconClass = compact ? "h-3 w-3" : "h-3.5 w-3.5";

  return (
    <div
      className={`flex shrink-0 items-center gap-0.5 ${compact ? "opacity-100 lg:opacity-0 lg:group-hover:opacity-100 lg:group-focus-within:opacity-100" : "opacity-100"}`}
    >
      <button
        type="button"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          onRename();
        }}
        className={btnClass}
        title="重命名"
        aria-label="重命名会话"
      >
        <Pencil className={iconClass} />
      </button>
      <button
        type="button"
        disabled={disabled}
        onClick={(e) => {
          e.stopPropagation();
          onDelete();
        }}
        className={`${btnClass} hover:text-red-600`}
        title="删除"
        aria-label="删除会话"
      >
        <Trash2 className={iconClass} />
      </button>
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
