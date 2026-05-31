import type { NavigateFunction } from "react-router-dom";

import { getKnowledgeItem } from "@/services/knowledgeItems";

export type InlineCitationSource = {
  index: number;
  item_id?: string | null;
  document_id?: string | null;
  page?: number | null;
};

export function buildDocumentPreviewUrl(kbId: string, docId: string, page?: number | null): string {
  const sp = new URLSearchParams();
  sp.set("kbId", kbId);
  sp.set("docId", docId);
  if (page != null && page >= 0) sp.set("page", String(page));
  return `/documents?${sp.toString()}`;
}

/** 根据 RAG / 报告引用编号打开知识库原文或条目详情 */
export async function openRagCitation(
  kbId: string,
  citation: InlineCitationSource,
  nav: NavigateFunction,
): Promise<void> {
  if (!citation.item_id && !citation.document_id) return;

  if (citation.document_id) {
    nav(buildDocumentPreviewUrl(kbId, citation.document_id, citation.page));
    return;
  }

  if (!citation.item_id) return;

  const item = await getKnowledgeItem(kbId, citation.item_id);
  if (item.document_id) {
    const page = citation.page ?? item.page;
    nav(buildDocumentPreviewUrl(kbId, item.document_id, page));
    return;
  }
  nav(`/documents/items/${kbId}/${citation.item_id}`);
}

export function citationByIndex<T extends InlineCitationSource>(
  sources: T[] | undefined,
  index: number,
): T | undefined {
  return sources?.find((s) => s.index === index);
}
