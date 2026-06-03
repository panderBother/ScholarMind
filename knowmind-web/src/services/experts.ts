import { apiFetch, parseApiError } from "@/services/http";
import type { ChatStreamHandlers, RagSourceDto } from "@/services/chat";

export type ExpertDto = {
  id: string;
  kb_id: string;
  name: string;
  description: string | null;
  system_prompt: string;
  created_at: string;
  updated_at: string;
};

export type ExpertCreateBody = {
  kb_id: string;
  name?: string;
  description?: string;
};

export type ExpertChatBody = {
  message: string;
  deep_research?: boolean;
  web_search?: boolean;
  arxiv?: boolean;
  semantic_scholar?: boolean;
  conversation_id?: string | null;
};

export async function listExperts(kbId?: string): Promise<ExpertDto[]> {
  const sp = kbId ? `?kb_id=${encodeURIComponent(kbId)}` : "";
  const res = await apiFetch(`/experts${sp}`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ExpertDto[];
}

export async function getExpert(expertId: string): Promise<ExpertDto> {
  const res = await apiFetch(`/experts/${expertId}`);
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ExpertDto;
}

export async function createExpert(body: ExpertCreateBody): Promise<ExpertDto> {
  const res = await apiFetch(`/experts`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ExpertDto;
}

export async function refreshExpert(expertId: string): Promise<ExpertDto> {
  const res = await apiFetch(`/experts/${expertId}/refresh`, { method: "POST" });
  if (!res.ok) throw new Error(await parseApiError(res));
  return (await res.json()) as ExpertDto;
}

export async function deleteExpert(expertId: string): Promise<void> {
  const res = await apiFetch(`/experts/${expertId}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await parseApiError(res));
}

/** 专家 Agent SSE 流式对话（与 chat/stream 事件格式一致） */
export async function streamExpertChat(
  expertId: string,
  body: ExpertChatBody,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await apiFetch(`/experts/${expertId}/chat/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify({
      message: body.message,
      deep_research: body.deep_research ?? false,
      web_search: body.web_search ?? false,
      arxiv: body.arxiv ?? false,
      semantic_scholar: body.semantic_scholar ?? false,
      conversation_id: body.conversation_id ?? null,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseApiError(res));
  }

  const reader = res.body?.getReader();
  if (!reader) throw new Error("响应体不可读");

  const decoder = new TextDecoder();
  let carry = "";

  const handleLine = (line: string) => {
    if (!line.startsWith("data:")) return;
    const jsonPart = line.slice(5).trimStart();
    if (!jsonPart) return;
    const msg = JSON.parse(jsonPart) as Record<string, unknown>;
    if (msg.type === "trace_id" && typeof msg.trace_id === "string") {
      handlers.onTraceId(msg.trace_id);
      return;
    }
    if (msg.type === "conversation_id" && typeof msg.conversation_id === "string") {
      handlers.onConversationId?.(msg.conversation_id, Boolean(msg.is_new));
      return;
    }
    if (msg.type === "agent_step" && typeof msg.step === "string") {
      const statusRaw = msg.status;
      const status =
        statusRaw === "running" || statusRaw === "done" || statusRaw === "error" || statusRaw === "skipped"
          ? statusRaw
          : "done";
      handlers.onAgentStep?.({
        step: msg.step,
        status,
        detail: typeof msg.detail === "string" ? msg.detail : undefined,
      });
      return;
    }
    if (msg.type === "thinking_delta" && typeof msg.text === "string") {
      handlers.onThinkingDelta?.(msg.text);
      return;
    }
    if (msg.type === "delta" && typeof msg.text === "string") {
      handlers.onDelta(msg.text);
      return;
    }
    if (msg.type === "error" && typeof msg.message === "string") {
      handlers.onError?.(msg.message);
      return;
    }
    if (msg.type === "rag_sources" && typeof msg.kb_id === "string" && Array.isArray(msg.sources)) {
      const sources = (msg.sources as RagSourceDto[]).filter(
        (s) => typeof s.index === "number" && typeof s.title === "string",
      );
      if (sources.length) handlers.onRagSources?.(msg.kb_id, sources);
      return;
    }
    if (msg.type === "done") {
      handlers.onDone();
      return "done" as const;
    }
    return null;
  };

  let finished = false;

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      carry += decoder.decode(value, { stream: true });
      const parts = carry.split("\n");
      carry = parts.pop() ?? "";
      for (const line of parts) {
        if (line.startsWith("data:")) {
          if (handleLine(line) === "done") {
            finished = true;
            break;
          }
        }
      }
      if (finished) break;
    }
    if (!finished && carry.trim()) {
      for (const line of carry.split("\n")) {
        if (line.startsWith("data:")) {
          if (handleLine(line) === "done") {
            finished = true;
            break;
          }
        }
      }
    }
    if (!finished) {
      handlers.onDone();
    }
  } finally {
    if (finished) {
      void reader.cancel().catch(() => undefined);
    }
    reader.releaseLock();
  }
}
