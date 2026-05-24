"""知识库混合检索：Chroma 向量 + Whoosh BM25 + RRF 融合 + BGE-Reranker 精排。"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.indexing.vector_factory import get_vector_index
from app.indexing.whoosh_index import whoosh_search
from app.ingest.embedding import embed_texts
from app.ingest.rerank import rerank_candidates
from app.models.orm import KnowledgeItem
from app.services.knowledge_base_service import get_knowledge_base
from app.services.rag_logging_service import distance_to_score

log = logging.getLogger(__name__)


class SearchError(Exception):
    def __init__(self, message: str, status_code: int) -> None:
        self.message = message
        self.status_code = status_code
        super().__init__(message)


@dataclass
class HybridSearchHit:
    item_id: str
    chunk_id: str
    doc_id: str
    title: str
    text: str
    snippet: str
    score: float
    source_type: str
    page: int | None
    tags: list[str]


def rrf_merge(
    *ranked_lists: list[dict[str, Any]],
    key: str = "chunk_id",
    k: int = 60,
) -> list[dict[str, Any]]:
    """Reciprocal Rank Fusion：多路检索结果去重融合。"""
    scores: dict[str, float] = {}
    merged: dict[str, dict[str, Any]] = {}

    for lst in ranked_lists:
        for rank, item in enumerate(lst, start=1):
            cid = str(item.get(key) or "")
            if not cid:
                continue
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            if cid not in merged:
                merged[cid] = dict(item)
            else:
                prev = merged[cid]
                if len(str(item.get("text") or "")) > len(str(prev.get("text") or "")):
                    merged[cid] = {**prev, **item}

    ordered = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)
    out: list[dict[str, Any]] = []
    for cid in ordered:
        row = dict(merged[cid])
        row["score"] = scores[cid]
        row["rrf_score"] = scores[cid]
        out.append(row)
    return out


def _snippet(text: str, max_len: int = 200) -> str:
    t = (text or "").strip().replace("\n", " ")
    if len(t) <= max_len:
        return t
    return t[:max_len] + "…"


def _tags_match(item_tags: list | None, required: list[str]) -> bool:
    if not required:
        return True
    have = {str(t).strip().lower() for t in (item_tags or []) if str(t).strip()}
    return all(r.strip().lower() in have for r in required)


async def _vector_hits(kb_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    hits: list[dict[str, Any]] = []
    try:
        q_vectors = await asyncio.to_thread(embed_texts, [query[:8000]])
        raw_vector = get_vector_index().query_similar(
            kb_id=kb_id,
            query_embedding=q_vectors[0],
            top_k=top_k,
        )
        for h in raw_vector:
            hits.append(
                {
                    "chunk_id": str(h.get("chunk_id") or ""),
                    "text": str(h.get("text") or ""),
                    "doc_id": str(h.get("doc_id") or ""),
                    "item_id": str(h.get("item_id") or ""),
                    "page": int(h.get("page") or 0),
                    "score": distance_to_score(h.get("distance")),
                    "vector_score": distance_to_score(h.get("distance")),
                },
            )
    except Exception as e:
        log.exception("hybrid_search vector failed: %s", e)
    return hits


def _bm25_hits(root: str, kb_id: str, query: str, top_k: int) -> list[dict[str, Any]]:
    rows = whoosh_search(
        root,
        kb_id=kb_id,
        query=query,
        top_k=top_k,
        lifecycle_status="published",
    )
    for h in rows:
        h["bm25_score"] = h.get("score")
    return rows


def _fuse_candidates(
    vector_hits: list[dict[str, Any]],
    bm25_hits: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], set[str], dict[str, float]]:
    """RRF 融合；无 BM25 命中时仍保留向量路（供 Rerank 精排）。"""
    bm25_ids = {str(h.get("chunk_id") or "") for h in bm25_hits}
    vector_score_by_id = {
        str(h.get("chunk_id") or ""): float(h.get("score") or 0) for h in vector_hits
    }

    if vector_hits and bm25_hits:
        fused = rrf_merge(vector_hits, bm25_hits)
    elif bm25_hits:
        fused = rrf_merge(bm25_hits)
    elif vector_hits:
        top_vector = max(vector_hits, key=lambda h: float(h.get("score") or 0))
        if float(top_vector.get("score") or 0) >= 0.55:
            fused = rrf_merge(vector_hits)
        else:
            fused = []
    else:
        fused = []

    return fused, bm25_ids, vector_score_by_id


def _passes_relevance_gate(
    chunk_id: str,
    *,
    bm25_ids: set[str],
    vector_score_by_id: dict[str, float],
    rerank_applied: bool,
) -> bool:
    settings = get_settings()
    if rerank_applied:
        return True
    if chunk_id in bm25_ids:
        return True
    return vector_score_by_id.get(chunk_id, 0) >= 0.35


async def hybrid_search(
    session: AsyncSession,
    user_id: str,
    kb_id: str,
    q: str,
    *,
    limit: int = 20,
    category_id: str | None = None,
    tags: list[str] | None = None,
    rerank: bool | None = None,
) -> list[HybridSearchHit]:
    """
    混合检索主流程：
    1. Chroma 语义 Top-K（BGE-M3）
    2. Whoosh BM25 关键词 Top-K
    3. RRF 融合
    4. BGE-Reranker 精排（可配置关闭）
    5. MySQL 补全元数据 + 分类/标签筛选
    """
    query = (q or "").strip()
    if not query:
        raise SearchError("检索词不能为空", 422)

    await get_knowledge_base(session, user_id, kb_id)

    settings = get_settings()
    cap = max(1, min(int(limit), 50))
    candidate_k = min(64, max(settings.rag_candidate_k, cap * 2))

    vector_hits, bm25_hits = await asyncio.gather(
        _vector_hits(kb_id, query, candidate_k),
        asyncio.to_thread(
            _bm25_hits,
            settings.whoosh_index_root,
            kb_id,
            query,
            candidate_k,
        ),
    )

    fused, bm25_ids, vector_score_by_id = _fuse_candidates(vector_hits, bm25_hits)
    embed_mode = (settings.embedding_mode or "bge").strip().lower()
    do_rerank = rerank if rerank is not None else settings.rerank_enabled
    if do_rerank and embed_mode != "hash" and fused:
        reranked = await asyncio.to_thread(rerank_candidates, query, fused)
    else:
        reranked = fused
    rerank_applied = bool(
        do_rerank
        and embed_mode != "hash"
        and reranked
        and any(r.get("rerank_score") is not None for r in reranked),
    )
    trimmed = reranked[:cap]

    item_ids = [str(h.get("item_id") or "") for h in trimmed if h.get("item_id")]
    items_by_id: dict[str, KnowledgeItem] = {}
    if item_ids:
        stmt = select(KnowledgeItem).where(
            KnowledgeItem.kb_id == kb_id,
            KnowledgeItem.id.in_(item_ids),
        )
        rows = await session.execute(stmt)
        for item in rows.scalars().all():
            items_by_id[item.id] = item

    tag_filter = [t for t in (tags or []) if t.strip()]
    results: list[HybridSearchHit] = []

    for h in trimmed:
        item_id = str(h.get("item_id") or "")
        item = items_by_id.get(item_id) if item_id else None

        if category_id and item is not None and item.category_id != category_id:
            continue
        if item is not None and not _tags_match(item.tags, tag_filter):
            continue

        text = str(h.get("text") or "")
        doc_id = str(h.get("doc_id") or "")
        if item is not None:
            title = item.title
            source_type = item.source_type
            page = item.page if item.page is not None else int(h.get("page") or 0)
            item_tags = [str(t) for t in (item.tags or [])]
            if not doc_id and item.document_id:
                doc_id = str(item.document_id)
            snippet = _snippet(text or item.content or item.summary or "")
        else:
            title = _snippet(text, 80) or "未命名片段"
            source_type = "document" if doc_id else "unknown"
            page = int(h.get("page") or 0)
            item_tags = []
            snippet = _snippet(text)

        if not item_id:
            item_id = str(h.get("chunk_id") or "")

        cid = str(h.get("chunk_id") or "")
        if not _passes_relevance_gate(
            cid,
            bm25_ids=bm25_ids,
            vector_score_by_id=vector_score_by_id,
            rerank_applied=rerank_applied,
        ):
            continue

        results.append(
            HybridSearchHit(
                item_id=item_id,
                chunk_id=cid,
                doc_id=doc_id,
                title=title,
                text=text,
                snippet=snippet,
                score=float(h.get("score") or 0.0),
                source_type=source_type,
                page=page if page >= 0 else None,
                tags=item_tags,
            ),
        )
        if len(results) >= cap:
            break

    log.info(
        "hybrid_search kb=%s vec=%s bm25=%s fused=%s rerank=%s out=%s",
        kb_id,
        len(vector_hits),
        len(bm25_hits),
        len(fused),
        rerank_applied,
        len(results),
    )
    return results
