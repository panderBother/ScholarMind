"""文档入库状态机，统一约束预览、排队、处理、完成与失败流转。"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol


class DocumentStatus(StrEnum):
    PREVIEW = "preview"
    PENDING = "pending"
    PROCESSING = "processing"
    DONE = "done"
    FAILED = "failed"


_ALLOWED_TRANSITIONS: dict[DocumentStatus, frozenset[DocumentStatus]] = {
    DocumentStatus.PREVIEW: frozenset({DocumentStatus.PENDING, DocumentStatus.FAILED}),
    DocumentStatus.PENDING: frozenset({DocumentStatus.PROCESSING, DocumentStatus.FAILED}),
    DocumentStatus.PROCESSING: frozenset(
        {DocumentStatus.PENDING, DocumentStatus.DONE, DocumentStatus.FAILED}
    ),
    DocumentStatus.FAILED: frozenset({DocumentStatus.PENDING}),
    DocumentStatus.DONE: frozenset({DocumentStatus.PENDING}),
}


class DocumentStateRow(Protocol):
    status: str
    parse_progress: int
    parse_stage: str | None
    error_message: str | None


def transition_document(
    document: DocumentStateRow,
    target: DocumentStatus,
    *,
    progress: int | None = None,
    stage: str | None = None,
    error: str | None = None,
) -> None:
    current = DocumentStatus(document.status)
    if target != current and target not in _ALLOWED_TRANSITIONS[current]:
        raise ValueError(f"invalid document transition: {current.value} -> {target.value}")

    document.status = target.value
    if progress is not None:
        document.parse_progress = max(0, min(100, int(progress)))
    if stage is not None:
        document.parse_stage = stage[:64] or None
    document.error_message = error[:4000] if error else None
