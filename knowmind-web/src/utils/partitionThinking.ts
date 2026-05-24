/**
 * 部分服务商不把推理放在 reasoning_content，而是塞进正文里的 XML 标签。
 * 流式拼接时需反复解析：完整块从正文移除；未闭合块之后的内容暂视为推理，不进入 Markdown。
 */

/** 常见推理标签名（与模型 / Chat 模板一致；按需追加） */
const THINKING_TAG_NAMES = ["think", "redacted_thinking", "reasoning"] as const;

const PAIRS: ReadonlyArray<[RegExp, RegExp]> = THINKING_TAG_NAMES.map((tag) => [
  new RegExp(`<${tag}\\b[^>]*>`, "i"),
  new RegExp(`</${tag}>`, "i"),
]);

export function partitionThinkingBlocks(raw: string): { visible: string; thinking: string } {
  const thinkingParts: string[] = [];
  let out = "";
  let i = 0;

  while (i < raw.length) {
    let best: { abs: number; openLen: number; closeRe: RegExp } | null = null;
    const tail = raw.slice(i);
    for (const [openRe, closeRe] of PAIRS) {
      const om = tail.match(openRe);
      if (!om || om.index === undefined) continue;
      const abs = i + om.index;
      if (!best || abs < best.abs) {
        best = { abs, openLen: om[0].length, closeRe };
      }
    }

    if (!best) {
      out += raw.slice(i);
      break;
    }

    out += raw.slice(i, best.abs);
    const afterOpen = best.abs + best.openLen;
    const tail2 = raw.slice(afterOpen);
    const cm = tail2.match(best.closeRe);
    if (!cm || cm.index === undefined) {
      thinkingParts.push(tail2);
      break;
    }
    thinkingParts.push(tail2.slice(0, cm.index));
    i = afterOpen + cm.index + cm[0].length;
  }

  return {
    visible: out.replace(/\r\n/g, "\n").trimEnd(),
    thinking: thinkingParts.join("\n\n").trim(),
  };
}

export function mergeThinkingParts(sseThinking: string, tagThinking: string): string | undefined {
  const parts = [sseThinking.trim(), tagThinking.trim()].filter(Boolean);
  if (parts.length === 0) return undefined;
  return parts.join("\n\n—\n\n");
}
