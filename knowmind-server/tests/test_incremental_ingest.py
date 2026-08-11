from app.ingest.chunking import TextChunk
from app.models.orm import DocumentChunk
from app.workers.document_tasks import _chunk_hash, plan_incremental_chunks


def _stored(chunk_id: str, text: str, page: int, ordinal: int) -> DocumentChunk:
    return DocumentChunk(
        document_id="doc1",
        chunk_id=chunk_id,
        content_hash=_chunk_hash(text, page),
        ordinal=ordinal,
        page=page,
        text=text,
    )


def test_incremental_plan_reuses_unchanged_chunk_and_only_embeds_changed() -> None:
    old = [_stored("keep", "unchanged", 0, 0), _stored("remove", "old", 0, 1)]
    new = [TextChunk("unchanged", 0), TextChunk("new content", 0)]

    assignments, removed = plan_incremental_chunks(
        document_id="doc1",
        new_chunks=new,
        old_chunks=old,
    )

    assert assignments[0].chunk_id == "keep"
    assert assignments[0].requires_embedding is False
    assert assignments[1].requires_embedding is True
    assert removed == ["remove"]


def test_incremental_plan_identical_document_requires_no_embedding() -> None:
    old = [_stored("a", "one", 0, 0), _stored("b", "two", 1, 1)]
    new = [TextChunk("one", 0), TextChunk("two", 1)]

    assignments, removed = plan_incremental_chunks(
        document_id="doc1",
        new_chunks=new,
        old_chunks=old,
    )

    assert all(not assignment.requires_embedding for assignment in assignments)
    assert [assignment.chunk_id for assignment in assignments] == ["a", "b"]
    assert removed == []
