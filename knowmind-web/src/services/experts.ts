import { getAccessToken } from "@/services/auth";
import type { ChatStreamHandlers, RagSourceDto } from "@/services/chat";

const BASE = "/api/v1";

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
  conversation_id?: string | null;
};

function authHeaders(json = false): HeadersInit {
  const token = getAccessToken();
  if (!token) throw new Error("未登录");
  const h: HeadersInit = { Authorization: `Bearer ${token}` };
  if (json) h["Content-Type"] = "application/json";
  return h;
}

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function listExperts(kbId?: string): Promise<ExpertDto[]> {
  const sp = kbId ? `?kb_id=${encodeURIComponent(kbId)}` : "";
  const res = await fetch(`${BASE}/experts${sp}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ExpertDto[];
}

export async function getExpert(expertId: string): Promise<ExpertDto> {
  const res = await fetch(`${BASE}/experts/${expertId}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ExpertDto;
}

export async function createExpert(body: ExpertCreateBody): Promise<ExpertDto> {
  const res = await fetch(`${BASE}/experts`, {
    method: "POST",
    headers: authHeaders(true),
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ExpertDto;
}

export async function refreshExpert(expertId: string): Promise<ExpertDto> {
  const res = await fetch(`${BASE}/experts/${expertId}/refresh`, {
    method: "POST",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as ExpertDto;
}

export async function deleteExpert(expertId: string): Promise<void> {
  const res = await fetch(`${BASE}/experts/${expertId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error(await parseError(res));
}

/** 专家 Agent SSE 流式对话（与 chat/stream 事件格式一致） */
export async function streamExpertChat(
  expertId: string,
  body: ExpertChatBody,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const res = await fetch(`${BASE}/experts/${expertId}/chat/stream`, {
    method: "POST",
    headers: {
      ...authHeaders(true),
      Accept: "text/event-stream",
    },
    body: JSON.stringify({
      message: body.message,
      deep_research: body.deep_research ?? false,
      conversation_id: body.conversation_id ?? null,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
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
    if (msg.type === "done") handlers.onDone();
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      carry += decoder.decode(value, { stream: true });
      const parts = carry.split("\n");
      carry = parts.pop() ?? "";
      for (const line of parts) {
        if (line.startsWith("data:")) handleLine(line);
      }
    }
    if (carry.trim()) {
      for (const line of carry.split("\n")) {
        if (line.startsWith("data:")) handleLine(line);
      }
    }
  } finally {
    reader.releaseLock();
  }
}
