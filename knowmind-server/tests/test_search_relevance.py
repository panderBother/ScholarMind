"""检索相关度门槛与语义分展示（避免 RRF 分被误标为「相关度 0.02」）。"""

from app.services.search_service import (
    _passes_relevance_gate,
    _semantic_relevance_score,
)


def test_semantic_score_prefers_rerank_over_rrf() -> None:
    h = {"chunk_id": "c1", "score": 0.02, "rrf_score": 0.02, "rerank_score": 0.82}
    assert _semantic_relevance_score(h, {}) == 0.82


def test_semantic_score_uses_vector_not_rrf() -> None:
    h = {"chunk_id": "c1", "score": 0.02, "rrf_score": 0.02}
    assert _semantic_relevance_score(h, {"c1": 0.61}) == 0.61


def test_gate_rejects_bm25_only_weak_vector_in_bge_mode() -> None:
    h = {"chunk_id": "c1", "score": 0.02}
    assert not _passes_relevance_gate(
        "c1",
        bm25_ids={"c1"},
        bm25_score_by_id={"c1": 0.9},
        vector_score_by_id={"c1": 0.08},
        rerank_applied=False,
        h=h,
        embed_mode="bge",
        allow_keyword_fallback=False,
    )


def test_gate_accepts_bm25_keyword_in_admin_search() -> None:
    h = {"chunk_id": "c1", "score": 0.02}
    assert _passes_relevance_gate(
        "c1",
        bm25_ids={"c1"},
        bm25_score_by_id={"c1": 0.82},
        vector_score_by_id={"c1": 0.08},
        rerank_applied=False,
        h=h,
        embed_mode="bge",
        allow_keyword_fallback=True,
    )


def test_gate_accepts_strong_vector_without_bm25() -> None:
    h = {"chunk_id": "c1", "score": 0.02}
    assert _passes_relevance_gate(
        "c1",
        bm25_ids=set(),
        bm25_score_by_id={},
        vector_score_by_id={"c1": 0.72},
        rerank_applied=False,
        h=h,
        embed_mode="bge",
        allow_keyword_fallback=True,
    )


def test_gate_accepts_bm25_in_hash_mode() -> None:
    h = {"chunk_id": "c1", "score": 0.02}
    assert _passes_relevance_gate(
        "c1",
        bm25_ids={"c1"},
        bm25_score_by_id={"c1": 0.5},
        vector_score_by_id={"c1": 0.01},
        rerank_applied=False,
        h=h,
        embed_mode="hash",
        allow_keyword_fallback=True,
    )


def test_gate_checks_rerank_score_when_applied() -> None:
    h = {"chunk_id": "c1", "rerank_score": 0.12, "score": 0.12}
    assert not _passes_relevance_gate(
        "c1",
        bm25_ids=set(),
        bm25_score_by_id={},
        vector_score_by_id={"c1": 0.9},
        rerank_applied=True,
        h=h,
        embed_mode="bge",
        allow_keyword_fallback=True,
    )


def test_filter_confident_rag_hits_drops_weak_tail() -> None:
    from app.services.rag_logging_service import RagHit, filter_confident_rag_hits

    hits = [
        RagHit("c1", "a", "d", "i1", 0, 0.82),
        RagHit("c2", "b", "d", "i2", 0, 0.78),
        RagHit("c3", "c", "d", "i3", 0, 0.35),
    ]
    out = filter_confident_rag_hits(hits, min_top_score=0.5, relative_to_top=0.75)
    assert len(out) == 2
    assert out[0].score == 0.82


def test_filter_confident_rag_hits_empty_when_top_weak() -> None:
    from app.services.rag_logging_service import RagHit, filter_confident_rag_hits

    hits = [RagHit("c1", "a", "d", "i1", 0, 0.41)]
    assert filter_confident_rag_hits(hits, min_top_score=0.5) == []


def test_strict_fusion_allows_strong_bm25_when_vector_weak() -> None:
    from app.services.search_service import _fuse_candidates

    vector_hits = [{"chunk_id": "v1", "score": 0.22, "text": "weak vec"}]
    bm25_hits = [{"chunk_id": "b1", "score": 0.88, "text": "strong keyword"}]
    fused, bm25_ids, _ = _fuse_candidates(vector_hits, bm25_hits, embed_mode="bge", strict=True)
    assert len(fused) >= 1
    assert "b1" in bm25_ids


def test_strict_fusion_blocks_weak_both() -> None:
    from app.services.search_service import _fuse_candidates

    vector_hits = [{"chunk_id": "v1", "score": 0.22, "text": "weak vec"}]
    bm25_hits = [{"chunk_id": "b1", "score": 0.12, "text": "weak kw"}]
    fused, _, _ = _fuse_candidates(vector_hits, bm25_hits, embed_mode="bge", strict=True)
    assert fused == []

