import { ExternalLink, Link2 } from "lucide-react";

import { MarkdownPreview } from "@/components/MarkdownPreview";
import type { KnowledgeItemDto } from "@/services/knowledgeItems";

export type UrlPreviewDto = {
  url: string;
  page_title: string | null;
  title: string;
  summary: string | null;
  content: string;
};

type Props =
  | {
      mode: "item";
      item: KnowledgeItemDto;
      onClose: () => void;
    }
  | {
      mode: "preview";
      preview: UrlPreviewDto;
      onClose: () => void;
    };

/** URL / 条目只读预览（不可编辑） */
export function ItemPreviewDrawer(props: Props) {
  const title = props.mode === "item" ? props.item.title : props.preview.title;
  const summary = props.mode === "item" ? props.item.summary : props.preview.summary;
  const content = props.mode === "item" ? props.item.content : props.preview.content;
  const sourceUrl = props.mode === "item" ? props.item.source : props.preview.url;
  const pageTitle = props.mode === "preview" ? props.preview.page_title : null;
  const readonly = props.mode === "item" ? props.item.source_type === "url" : true;

  return (
    <div className="fixed inset-0 z-[95] flex justify-end bg-black/40" onClick={props.onClose}>
      <div
        className="flex h-full w-full max-w-3xl flex-col bg-white shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex flex-wrap items-start justify-between gap-3 border-b px-4 py-3">
          <div className="min-w-0 flex-1">
            <div className="flex items-center gap-2">
              <Link2 className="h-5 w-5 shrink-0 text-violet-500" />
              <h2 className="truncate font-semibold text-slate-900">{title}</h2>
            </div>
            {pageTitle ? <p className="mt-1 text-xs text-slate-500">原网页标题：{pageTitle}</p> : null}
            {readonly ? (
              <span className="mt-2 inline-block rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                只读预览 · 不可修改
              </span>
            ) : null}
          </div>
          <div className="flex shrink-0 gap-2">
            {sourceUrl ? (
              <a
                href={sourceUrl}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-3 py-1.5 text-sm text-slate-700 hover:bg-slate-50"
              >
                <ExternalLink className="h-4 w-4" />
                打开原网页
              </a>
            ) : null}
            <button type="button" onClick={props.onClose} className="rounded-lg px-3 py-1.5 text-sm text-slate-500">
              关闭
            </button>
          </div>
        </div>

        {summary ? (
          <p className="border-b border-slate-100 bg-slate-50/80 px-4 py-3 text-sm text-slate-600">{summary}</p>
        ) : null}

        <div className="min-h-0 flex-1 overflow-y-auto px-4 py-4">
          <p className="mb-2 text-xs font-medium text-slate-500">Markdown 预览</p>
          <div className="rounded-xl border border-slate-200 bg-slate-50/50 p-4">
            <MarkdownPreview markdown={content || "（空）"} />
          </div>
          {content ? (
            <p className="mt-2 text-xs text-slate-400">共 {content.length.toLocaleString()} 字</p>
          ) : null}
        </div>
      </div>
    </div>
  );
}
