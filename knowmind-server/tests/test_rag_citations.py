from app.services.rag_citations import hits_to_source_payload
from app.services.rag_logging_service import RagHit


def test_hits_to_source_payload() -> None:
    hits = [
        RagHit(
            chunk_id="c1",
            text="x" * 500,
            doc_id="d1",
            item_id="i1",
            page=2,
            score=0.87,
        ),
    ]
    out = hits_to_source_payload(hits, {"i1": "测试条目"})
    assert len(out) == 1
    assert out[0]["index"] == 1
    assert out[0]["title"] == "测试条目"
    assert out[0]["item_id"] == "i1"
    assert out[0]["document_id"] == "d1"
    assert len(out[0]["snippet"]) <= 403
    assert "第 3 页" in (out[0]["meta"] or "")
