from app.ingest.rerank import rerank_candidates


def test_rerank_skipped_in_hash_mode(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODE", "hash")
    from app.core.config import get_settings

    get_settings.cache_clear()

    cands = [
        {"chunk_id": "a", "text": "first", "score": 0.1},
        {"chunk_id": "b", "text": "second", "score": 0.2},
    ]
    out = rerank_candidates("query", cands)
    assert out[0]["chunk_id"] == "a"
    assert "rerank_score" not in out[0]

    get_settings.cache_clear()


def test_rerank_http_mode(monkeypatch) -> None:
    monkeypatch.setenv("EMBEDDING_MODE", "http")
    monkeypatch.setenv("RERANK_MODE", "http")
    monkeypatch.setenv("EDGEFN_API_KEY", "test-key")
    monkeypatch.setenv("EDGEFN_API_BASE_URL", "https://api.edgefn.net/v1")

    from app.core.config import get_settings

    get_settings.cache_clear()

    def _fake_http(query: str, documents: list[str]) -> list[float]:
        assert query == "query"
        assert documents == ["first", "second"]
        return [0.1, 0.9]

    monkeypatch.setattr("app.ingest.rerank._rerank_http_scores", _fake_http)

    cands = [
        {"chunk_id": "a", "text": "first", "score": 0.2},
        {"chunk_id": "b", "text": "second", "score": 0.1},
    ]
    out = rerank_candidates("query", cands)
    assert out[0]["chunk_id"] == "b"
    assert out[0]["rerank_score"] == 0.9

    get_settings.cache_clear()
