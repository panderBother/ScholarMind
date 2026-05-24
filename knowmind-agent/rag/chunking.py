from dataclasses import dataclass


@dataclass
class Chunk:
    """单个文本块：携带来源元数据，便于溯源与重排。"""

    text: str
    doc_id: str
    page: int | None = None


def chunk_text(text: str, max_chars: int = 1200, overlap: int = 150) -> list[Chunk]:
    """
    简单滑窗切块（占位）：生产环境建议按结构（章节/段落）+ token 上限组合策略。
    """
    if not text.strip():
        return []
    chunks: list[Chunk] = []
    start = 0
    doc_id = "unknown"
    while start < len(text):
        end = min(len(text), start + max_chars)
        chunks.append(Chunk(text=text[start:end], doc_id=doc_id, page=None))
        if end == len(text):
            break
        start = end - overlap
    return chunks
