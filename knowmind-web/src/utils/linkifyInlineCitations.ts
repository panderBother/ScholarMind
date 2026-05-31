/** 将正文中的 [1]、[^2] 转为可点击锚点链接（供 Streamdown 渲染） */

const CITE_HASH_PREFIX = "#km-cite-";

const BRACKET_CITE = /\[(\d{1,2})\](?!\()/g;
const FOOTNOTE_CITE = /\[\^(\d{1,2})\]/g;

function splitFencedCodeBlocks(text: string): Array<{ code: boolean; value: string }> {
  const parts: Array<{ code: boolean; value: string }> = [];
  const re = /```[\s\S]*?```/g;
  let last = 0;
  for (const m of text.matchAll(re)) {
    const start = m.index ?? 0;
    if (start > last) parts.push({ code: false, value: text.slice(last, start) });
    parts.push({ code: true, value: m[0] });
    last = start + m[0].length;
  }
  if (last < text.length) parts.push({ code: false, value: text.slice(last) });
  if (!parts.length) parts.push({ code: false, value: text });
  return parts;
}

function replaceCitations(segment: string, valid: Set<number>): string {
  const toLink = (num: string, raw: string) => {
    const n = Number.parseInt(num, 10);
    if (!valid.has(n)) return raw;
    return `[${raw.slice(1, -1)}](${CITE_HASH_PREFIX}${n})`;
  };
  return segment
    .replace(FOOTNOTE_CITE, (raw, num) => toLink(num, raw))
    .replace(BRACKET_CITE, (raw, num) => toLink(num, raw));
}

export function linkifyInlineCitations(markdown: string, sourceIndices: Iterable<number>): string {
  const valid = new Set(sourceIndices);
  if (!valid.size || !markdown.trim()) return markdown;

  return splitFencedCodeBlocks(markdown)
    .map((part) => (part.code ? part.value : replaceCitations(part.value, valid)))
    .join("");
}

export function isCitationHash(href: string): boolean {
  try {
    const hash = href.startsWith("#") ? href : new URL(href, "http://local").hash;
    return hash.startsWith(CITE_HASH_PREFIX);
  } catch {
    return false;
  }
}

export function citationIndexFromHash(href: string): number | null {
  try {
    const hash = href.startsWith("#") ? href : new URL(href, "http://local").hash;
    if (!hash.startsWith(CITE_HASH_PREFIX)) return null;
    const n = Number.parseInt(hash.slice(CITE_HASH_PREFIX.length), 10);
    return Number.isFinite(n) ? n : null;
  } catch {
    return null;
  }
}
