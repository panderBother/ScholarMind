from dataclasses import dataclass

import pytest

from app.ingest.document_state import DocumentStatus, transition_document


@dataclass
class FakeDocument:
    status: str = "preview"
    parse_progress: int = 100
    parse_stage: str | None = "待确认"
    error_message: str | None = None


def test_document_state_happy_path() -> None:
    doc = FakeDocument()
    transition_document(doc, DocumentStatus.PENDING, progress=0, stage="排队中")
    transition_document(doc, DocumentStatus.PROCESSING, progress=5, stage="开始解析")
    transition_document(doc, DocumentStatus.DONE, progress=100, stage="完成")
    assert doc.status == "done"
    assert doc.parse_progress == 100
    assert doc.parse_stage == "完成"


def test_document_state_rejects_invalid_transition() -> None:
    doc = FakeDocument(status="done")
    with pytest.raises(ValueError, match="done -> processing"):
        transition_document(doc, DocumentStatus.PROCESSING)


def test_document_state_allows_done_to_pending_for_incremental_reindex() -> None:
    doc = FakeDocument(status="done", parse_progress=100, parse_stage="完成")
    transition_document(doc, DocumentStatus.PENDING, progress=0, stage="增量更新排队中")
    assert doc.status == "pending"
    assert doc.parse_progress == 0
