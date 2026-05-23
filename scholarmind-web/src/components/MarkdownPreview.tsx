import { memo } from "react";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { cjk } from "@streamdown/cjk";

const plugins = { code, cjk };

type Props = {
  markdown: string;
  className?: string;
};

/** 静态 Markdown 预览：URL 采集 / 条目只读预览 / 编辑侧栏 */
export const MarkdownPreview = memo(function MarkdownPreview({ markdown, className = "" }: Props) {
  return (
    <div
      className={`markdown-preview-root text-sm leading-relaxed text-slate-800 [&_.streamdown]:max-w-none ${className}`.trim()}
    >
      <Streamdown
        mode="static"
        plugins={plugins}
        shikiTheme={["github-light", "github-dark"]}
        controls={{ code: { copy: true, download: true } }}
        className="streamdown-static"
      >
        {markdown || "（空）"}
      </Streamdown>
    </div>
  );
});
