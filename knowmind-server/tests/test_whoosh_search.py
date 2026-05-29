from pathlib import Path

import pytest

from app.indexing.whoosh_index import whoosh_search, whoosh_upsert_chunks


@pytest.fixture
def whoosh_root(tmp_path: Path) -> Path:
    return tmp_path / "whoosh"


def test_whoosh_search_published_hits(whoosh_root: Path) -> None:
    kb_id = "kb-test-1"
    rows = [
        {
            "chunk_id": "c-pub-1",
            "kb_id": kb_id,
            "user_id": "u1",
            "doc_id": "",
            "item_id": "item-1",
            "page": 0,
            "text": "Transformer 注意力机制在 NLP 中广泛应用",
            "lifecycle_status": "published",
        },
        {
            "chunk_id": "c-pub-2",
            "kb_id": kb_id,
            "user_id": "u1",
            "doc_id": "",
            "item_id": "item-2",
            "page": 1,
            "text": "卷积神经网络用于图像识别",
            "lifecycle_status": "published",
        },
        {
            "chunk_id": "c-draft-1",
            "kb_id": kb_id,
            "user_id": "u1",
            "doc_id": "",
            "item_id": "item-3",
            "page": 0,
            "text": "草稿独有词汇 ZetaDraftKeyword",
            "lifecycle_status": "draft",
        },
    ]
    whoosh_upsert_chunks(whoosh_root, rows)

    hits = whoosh_search(whoosh_root, kb_id=kb_id, query="Transformer", top_k=10)
    assert len(hits) >= 1
    assert hits[0]["chunk_id"] == "c-pub-1"
    assert hits[0]["item_id"] == "item-1"

    draft_hits = whoosh_search(whoosh_root, kb_id=kb_id, query="ZetaDraftKeyword", top_k=10)
    assert draft_hits == []

    whoosh_upsert_chunks(
        whoosh_root,
        [
            {
                "chunk_id": "c-arch-1",
                "kb_id": kb_id,
                "user_id": "u1",
                "doc_id": "",
                "item_id": "item-arch",
                "page": 0,
                "text": "ArchivedOnlyKeywordXYZ",
                "lifecycle_status": "archived",
            },
        ],
    )
    archived_only = whoosh_search(whoosh_root, kb_id=kb_id, query="ArchivedOnlyKeywordXYZ", top_k=10)
    assert archived_only == []

    empty = whoosh_search(whoosh_root, kb_id=kb_id, query="   ", top_k=10)
    assert empty == []


def test_rrf_merge_deduplicates() -> None:
    from app.services.search_service import rrf_merge

    a = [{"chunk_id": "x", "text": "a"}, {"chunk_id": "y", "text": "b"}]
    b = [{"chunk_id": "y", "text": "b longer"}, {"chunk_id": "z", "text": "c"}]
    merged = rrf_merge(a, b)
    ids = [m["chunk_id"] for m in merged]
    assert ids[0] == "y"
    assert len(ids) == 3
