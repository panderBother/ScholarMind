/**
 * 对话 API：同步 `POST /api/v1/chat`；流式 `POST /api/v1/chat/stream`（SSE）。
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

export type ChatToolResult = {
  tool: string;
  ok: boolean;
  result: Record<string, unknown>;
};

export type ChatRequestBody = {
  message: string;
  knowledge_base_id: string | null;
  deep_research: boolean;
  web_search: boolean;
  /** 启用服务端本地文件读写（OpenAI tools） */
  file_tools?: boolean;
  /** 续聊时传入；不传则服务端新建会话并在 SSE 中返回 conversation_id */
  conversation_id?: string | null;
};

export type ChatResponseBody = {
  reply: string;
  trace_id: string;
};

export type ChatStreamHandlers = {
  onTraceId: (traceId: string) => void;
  /** 多轮记忆：服务端新建或确认的会话 id */
  onConversationId?: (conversationId: string, isNew: boolean) => void;
  onDelta: (text: string) => void;
  /** 模型推理 / 思维链增量（如 reasoning_content） */
  onThinkingDelta?: (text: string) => void;
  /** 上游业务错误（后端仍会在其后发送 `done`） */
  onError?: (message: string) => void;
  /** 模型调用本地文件读写工具后的结果 */
  onToolResult?: (payload: ChatToolResult) => void;
  /** 服务端文件操作日志，如「已执行写入操作」 */
  onFileLog?: (message: string) => void;
  onDone: () => void;
};

async function parseError(res: Response): Promise<string> {
  try {
    const j = (await res.json()) as { detail?: unknown };
    const d = j.detail;
    if (typeof d === "string") return d;
    if (Array.isArray(d)) return d.map((x) => JSON.stringify(x)).join("; ");
    return res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function sendChatMessage(body: ChatRequestBody): Promise<ChatResponseBody> {
  const token = getAccessToken();
  const headers: HeadersInit = { "Content-Type": "application/json" };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}/chat`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message: body.message,
      knowledge_base_id: body.knowledge_base_id,
      deep_research: body.deep_research,
      web_search: body.web_search,
      file_tools: body.file_tools ?? true,
      conversation_id: body.conversation_id ?? null,
    }),
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }
  return (await res.json()) as ChatResponseBody;
}

/**
 * 消费 SSE：`data: {JSON}\n\n`，事件类型 trace_id | delta | done。
 */
export async function streamChatMessage(
  body: ChatRequestBody,
  handlers: ChatStreamHandlers,
  signal?: AbortSignal,
): Promise<void> {
  const token = getAccessToken();
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    Accept: "text/event-stream",
  };
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${BASE}/chat/stream`, {
    method: "POST",
    headers,
    body: JSON.stringify({
      message: body.message,
      knowledge_base_id: body.knowledge_base_id,
      deep_research: body.deep_research,
      web_search: body.web_search,
      file_tools: body.file_tools ?? true,
      conversation_id: body.conversation_id ?? null,
    }),
    signal,
  });

  if (!res.ok) {
    throw new Error(await parseError(res));
  }

  const reader = res.body?.getReader();
  if (!reader) {
    throw new Error("响应体不可读");
  }

  const decoder = new TextDecoder();
  let carry = "";

  const handleLine = (line: string) => {
    if (!line.startsWith("data:")) return;
    const jsonPart = line.slice(5).trimStart();
    if (!jsonPart) return;
    const msg = JSON.parse(jsonPart) as {
      type?: string;
      trace_id?: string;
      text?: string;
      message?: string;
    };
    if (msg.type === "trace_id" && typeof msg.trace_id === "string") {
      handlers.onTraceId(msg.trace_id);
      return;
    }
    if (msg.type === "conversation_id" && typeof (msg as { conversation_id?: string }).conversation_id === "string") {
      const cid = (msg as { conversation_id: string }).conversation_id;
      const isNew = Boolean((msg as { is_new?: boolean }).is_new);
      handlers.onConversationId?.(cid, isNew);
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
    if (msg.type === "file_log" && typeof (msg as { message?: string }).message === "string") {
      handlers.onFileLog?.((msg as { message: string }).message);
      return;
    }
    if (msg.type === "tool_result") {
      const tool = typeof (msg as { tool?: string }).tool === "string" ? (msg as { tool: string }).tool : "";
      const ok = Boolean((msg as { ok?: boolean }).ok);
      const result =
        typeof (msg as { result?: unknown }).result === "object" &&
        (msg as { result?: unknown }).result !== null
          ? ((msg as { result: Record<string, unknown> }).result as Record<string, unknown>)
          : {};
      handlers.onToolResult?.({ tool, ok, result });
      return;
    }
    if (msg.type === "done") {
      handlers.onDone();
    }
  };

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      carry += decoder.decode(value, { stream: true });
      const parts = carry.split("\n");
      carry = parts.pop() ?? "";
      for (const line of parts) {
        if (line.startsWith("data:")) {
          handleLine(line);
        }
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
