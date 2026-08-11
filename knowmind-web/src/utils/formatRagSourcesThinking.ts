import type { RagSourceDto } from "@/services/chat";

/** 将 RAG 命中格式化为思维链内可读的引用块（生成结束后仍保留） */
export function formatRagSourcesThinkingBlock(sources: RagSourceDto[]): string {
  if (!sources.length) return "";
  const lines = ["【知识库引用来源】", ""];
  for (const s of sources) {
    lines.push(`[${s.index}] ${s.title}`);
    if (s.meta) lines.push(s.meta);
    const snippet = (s.snippet ?? "").trim();
    if (snippet) lines.push(snippet);
    lines.push("");
  }
  return lines.join("\n").trimEnd();
}
