import { memo, useMemo } from "react";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { cjk } from "@streamdown/cjk";

import { useCitationLinkClick } from "@/hooks/useCitationLinkClick";
import type { InlineCitationSource } from "@/utils/openRagCitation";
import { linkifyInlineCitations } from "@/utils/linkifyInlineCitations";

const plugins = { code, cjk };

type Props = {
  markdown: string;
  className?: string;
  kbId?: string;
  citations?: InlineCitationSource[];
};

/** 静态 Markdown 预览：URL 采集 / 条目只读预览 / 报告正文 */
export const MarkdownPreview = memo(function MarkdownPreview({
  markdown,
  className = "",
  kbId,
  citations,
}: Props) {
  const body = useMemo(() => {
    if (!citations?.length) return markdown || "（空）";
    return linkifyInlineCitations(
      markdown || "（空）",
      citations.map((c) => c.index),
    );
  }, [citations, markdown]);

  const onCitationClick = useCitationLinkClick(kbId, citations);

  return (
    <div
      className={`markdown-preview-root text-sm leading-relaxed text-slate-800 [&_.streamdown]:max-w-none [&_a[href*='#km-cite-']]:font-semibold [&_a[href*='#km-cite-']]:text-primary [&_a[href*='#km-cite-']]:no-underline hover:[&_a[href*='#km-cite-']]:underline ${className}`.trim()}
      onClick={onCitationClick}
    >
      <Streamdown
        mode="static"
        plugins={plugins}
        shikiTheme={["github-light", "github-dark"]}
        controls={{ code: { copy: true, download: true } }}
        className="streamdown-static"
      >
        {body}
      </Streamdown>
    </div>
  );
});
