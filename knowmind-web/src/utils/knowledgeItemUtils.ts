import type { KnowledgeItemDto } from "@/services/knowledgeItems";

export const SOURCE_LABEL: Record<string, string> = {
  manual: "手动",
  document: "文档",
  url: "URL",
  ai_extract: "提炼",
  distill: "蒸馏",
};

/** URL 采集条目正文不可改，以保证与源站一致。 */
export function isKnowledgeItemContentReadonly(item: Pick<KnowledgeItemDto, "source_type">): boolean {
  return item.source_type === "url";
}

export function canDeleteKnowledgeItem(item: Pick<KnowledgeItemDto, "source_type">): boolean {
  return item.source_type === "manual" || item.source_type === "ai_extract" || item.source_type === "distill";
}

export function canArchiveKnowledgeItem(item: Pick<KnowledgeItemDto, "source_type" | "lifecycle_status">): boolean {
  return item.lifecycle_status === "published" && item.source_type === "manual";
}
