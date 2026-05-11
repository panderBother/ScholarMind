/**
 * 多轮对话会话：从后端恢复历史（刷新后保持同一会话）。
 */

import { getAccessToken } from "@/services/auth";

const BASE = "/api/v1";

/** localStorage key，与「新对话」清空逻辑一致 */
export const CHAT_CONVERSATION_STORAGE_KEY = "scholarmind_chat_conversation_id";

export type ConversationDto = {
  id: string;
  knowledge_base_id: string | null;
  deep_research: boolean;
  web_search: boolean;
  title: string | null;
  created_at: string;
  updated_at: string;
};

export type ChatMessageDto = {
  id: string;
  role: string;
  content: string;
  trace_id: string | null;
  created_at: string;
};

export function getStoredConversationId(): string | null {
  try {
    return localStorage.getItem(CHAT_CONVERSATION_STORAGE_KEY);
  } catch {
    return null;
  }
}

export function setStoredConversationId(id: string | null): void {
  try {
    if (id) localStorage.setItem(CHAT_CONVERSATION_STORAGE_KEY, id);
    else localStorage.removeItem(CHAT_CONVERSATION_STORAGE_KEY);
  } catch {
    /* private mode 等 */
  }
}

function authHeaders(): HeadersInit {
  const token = getAccessToken();
  const h: HeadersInit = {};
  if (token) h.Authorization = `Bearer ${token}`;
  return h;
}

export async function fetchConversation(conversationId: string): Promise<ConversationDto> {
  const res = await fetch(`${BASE}/conversations/${encodeURIComponent(conversationId)}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(res.status === 404 ? "会话不存在" : await res.text());
  }
  return (await res.json()) as ConversationDto;
}

export async function fetchConversationMessages(conversationId: string): Promise<ChatMessageDto[]> {
  const res = await fetch(`${BASE}/conversations/${encodeURIComponent(conversationId)}/messages`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ChatMessageDto[];
}

export async function listConversations(limit = 50): Promise<ConversationDto[]> {
  const res = await fetch(`${BASE}/conversations?limit=${encodeURIComponent(String(limit))}`, {
    headers: authHeaders(),
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  return (await res.json()) as ConversationDto[];
}
