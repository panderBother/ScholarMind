from dataclasses import dataclass


@dataclass
class RetrievedPassage:
    score: float
    text: str
    source: str


def bm25_placeholder(query: str, corpus: list[str], top_k: int = 5) -> list[RetrievedPassage]:
    """BM25 占位：接入 rank_bm25 或 Elasticsearch 后替换。"""
    _ = query
    return [
        RetrievedPassage(score=1.0 - i * 0.1, text=c, source=f"doc-{i}")
        for i, c in enumerate(corpus[:top_k])
    ]


def vector_search_placeholder(query: str, top_k: int = 8) -> list[RetrievedPassage]:
    """向量检索占位：接入 FAISS / Milvus + embedding 服务后替换。"""
    _ = query
    return [RetrievedPassage(score=0.9, text="(placeholder passage)", source="vector") for _ in range(top_k)]
