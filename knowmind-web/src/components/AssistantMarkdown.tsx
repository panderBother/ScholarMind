import { memo, useMemo } from "react";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { cjk } from "@streamdown/cjk";

import { useCitationLinkClick } from "@/hooks/useCitationLinkClick";
import type { InlineCitationSource } from "@/utils/openRagCitation";
import { linkifyInlineCitations } from "@/utils/linkifyInlineCitations";
import { prepareAssistantMarkdown } from "@/utils/prepareAssistantMarkdown";

/** 模块级单例，避免每次渲染新建插件实例 */
const plugins = { code, cjk };

type Props = {
  /** 已剥离思维链标签后的 Markdown 正文 */
  markdown: string;
  /** true：SSE 仍在输出，启用流式解析 / isAnimating */
  isStreaming: boolean;
  /** 知识库 id（与 citations 同时传入时，正文 [1] 可点击跳转） */
  kbId?: string;
  /** RAG 引用列表，index 与正文 [N] / [^N] 对应 */
  citations?: InlineCitationSource[];
};

/**
 * 助手气泡：Vercel Streamdown（面向 AI 流式 Markdown）+ Shiki 高亮 + CJK。
 * @see https://streamdown.ai/docs/usage
 */
export const AssistantMarkdown = memo(function AssistantMarkdown({
  markdown,
  isStreaming,
  kbId,
  citations,
}: Props) {
  const body = useMemo(() => {
    const prepared = prepareAssistantMarkdown(markdown);
    if (!citations?.length) return prepared;
    return linkifyInlineCitations(
      prepared,
      citations.map((c) => c.index),
    );
  }, [citations, markdown]);

  const onCitationClick = useCitationLinkClick(kbId, citations);

  return (
    <div
      className="streamdown-chat-root text-sm leading-relaxed text-slate-800 [&_.streamdown]:max-w-none [&_a[href*='#km-cite-']]:font-semibold [&_a[href*='#km-cite-']]:text-primary [&_a[href*='#km-cite-']]:no-underline hover:[&_a[href*='#km-cite-']]:underline"
      onClick={onCitationClick}
    >
      <Streamdown
        mode={isStreaming ? undefined : "static"}
        plugins={plugins}
        isAnimating={isStreaming}
        shikiTheme={["github-light", "github-dark"]}
        controls={{ code: { copy: true, download: true } }}
        className={isStreaming ? "streamdown-chat" : "streamdown-static"}
      >
        {body}
      </Streamdown>
    </div>
  );
});
