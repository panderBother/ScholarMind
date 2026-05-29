/**
 * 部分模型会把整段 Markdown 包在 ```markdown 围栏里输出。
 * Streamdown 会将其渲染为「带语法高亮的源码块」，而非标题/链接等预览。
 * 此处剥掉外层围栏，保留正文内真实的代码块（如 mermaid）。
 */

const OPEN_FENCE = /^```(?:markdown|md)\s*\n/i;
const CLOSE_FENCE = /\n```\s*$/;

function looksLikeMarkdownDoc(inner: string): boolean {
  const t = inner.trim();
  if (!t) return false;
  return (
    /^#{1,6}\s/m.test(t) ||
    /^\*\*[^*]+\*\*/m.test(t) ||
    /^-\s/m.test(t) ||
    /^\d+\.\s/m.test(t) ||
    /^\|.+\|/m.test(t)
  );
}

function unwrapMarkdownFence(text: string): string | null {
  const trimmed = text.trim();
  const openMatch = trimmed.match(OPEN_FENCE);
  if (!openMatch) return null;

  const inner = trimmed.slice(openMatch[0].length);
  if (CLOSE_FENCE.test(trimmed)) {
    return inner.replace(CLOSE_FENCE, "").trimEnd();
  }
  return inner.trimEnd();
}

export function prepareAssistantMarkdown(raw: string): string {
  const text = raw.replace(/\r\n/g, "\n");

  const unwrapped = unwrapMarkdownFence(text);
  if (unwrapped !== null) return unwrapped;

  const trimmed = text.trim();
  const plainOpen = trimmed.match(/^```\s*\n/);
  if (plainOpen && CLOSE_FENCE.test(trimmed)) {
    const inner = trimmed.slice(plainOpen[0].length).replace(CLOSE_FENCE, "");
    if (looksLikeMarkdownDoc(inner)) {
      return inner.trimEnd();
    }
  }

  return text;
}
