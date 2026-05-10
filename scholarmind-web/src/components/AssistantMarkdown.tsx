import { memo } from "react";
import { Streamdown } from "streamdown";
import { code } from "@streamdown/code";
import { cjk } from "@streamdown/cjk";

/** 模块级单例，避免每次渲染新建插件实例 */
const plugins = { code, cjk };

type Props = {
  /** 已剥离思维链标签后的 Markdown 正文 */
  markdown: string;
  /** true：SSE 仍在输出，启用流式解析 / isAnimating */
  isStreaming: boolean;
};

/**
 * 助手气泡：Vercel Streamdown（面向 AI 流式 Markdown）+ Shiki 高亮 + CJK。
 * @see https://streamdown.ai/docs/usage
 */
export const AssistantMarkdown = memo(function AssistantMarkdown({ markdown, isStreaming }: Props) {
  return (
    <div className="streamdown-chat-root text-sm leading-relaxed text-slate-800 [&_.streamdown]:max-w-none">
      <Streamdown
        mode="streaming"
        plugins={plugins}
        isAnimating={isStreaming}
        shikiTheme={["github-light", "github-dark"]}
        controls={{ code: { copy: true, download: true } }}
        className="streamdown-chat"
      >
        {markdown}
      </Streamdown>
    </div>
  );
});
