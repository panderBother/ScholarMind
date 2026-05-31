import clsx from "clsx";
import { ExternalLink, Loader2 } from "lucide-react";
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import type { RagSourceDto } from "@/services/chat";
import { openRagCitation } from "@/utils/openRagCitation";

type Props = {
  kbId: string;
  sources: RagSourceDto[];
};

export function ChatRagSources({ kbId, sources }: Props) {
  const nav = useNavigate();
  const [loadingId, setLoadingId] = useState<string | null>(null);

  if (!sources.length) return null;

  const openSource = async (c: RagSourceDto) => {
    if (!c.item_id && !c.document_id) return;
    const loadingKey = c.document_id ?? c.item_id ?? String(c.index);
    setLoadingId(loadingKey);
    try {
      await openRagCitation(kbId, c, nav);
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div className="mb-3 rounded-lg border border-sky-100 bg-sky-50/70 px-3 py-2">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-sky-800">引用来源 ({sources.length})</p>
      <ul className="mt-2 space-y-2">
        {sources.map((c) => {
          const canOpen = Boolean(c.item_id || c.document_id);
          const key = c.chunk_id ?? `${c.item_id}-${c.index}`;
          const loadingKey = c.document_id ?? c.item_id ?? String(c.index);
          return (
            <li key={key}>
              <article
                className={clsx(
                  "rounded-lg border border-sky-100 bg-white p-2.5",
                  canOpen && "cursor-pointer hover:border-primary/40 hover:shadow-sm",
                )}
                onClick={canOpen ? () => void openSource(c) : undefined}
                onKeyDown={
                  canOpen
                    ? (e) => {
                        if (e.key === "Enter") void openSource(c);
                      }
                    : undefined
                }
                role={canOpen ? "button" : undefined}
                tabIndex={canOpen ? 0 : undefined}
              >
                <div className="flex items-start gap-2">
                  <span className="shrink-0 rounded bg-primary/10 px-1.5 py-0.5 text-[10px] font-bold text-primary">
                    [{c.index}]
                  </span>
                  <div className="min-w-0 flex-1">
                    <h4 className="text-xs font-semibold text-slate-900">{c.title}</h4>
                    {c.meta ? <p className="mt-0.5 text-[10px] text-slate-500">{c.meta}</p> : null}
                    <p className="mt-1 line-clamp-3 text-[10px] leading-relaxed text-slate-600">{c.snippet}</p>
                    {canOpen ? (
                      <span className="mt-1.5 inline-flex items-center gap-1 text-[10px] font-medium text-primary">
                        {loadingId === loadingKey ? (
                          <Loader2 className="h-3 w-3 animate-spin" />
                        ) : (
                          <ExternalLink className="h-3 w-3" />
                        )}
                        {c.page != null ? `查看 PDF 第 ${c.page + 1} 页` : "查看原文"}
                      </span>
                    ) : null}
                  </div>
                </div>
              </article>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
