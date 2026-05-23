from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ReportCitationOut(BaseModel):
    index: int
    chunk_id: str | None = None
    item_id: str | None = None
    document_id: str | None = None
    title: str
    meta: str | None = None
    snippet: str
    page: int | None = None
    score: float | None = None


class GenerateReportRequest(BaseModel):
    kb_id: str = Field(min_length=1, max_length=36)
    title: str | None = Field(default=None, max_length=300)


class ResearchReportListItem(BaseModel):
    id: str
    kb_id: str
    conversation_id: str | None
    title: str
    summary: str | None
    status: str
    citation_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ResearchReportOut(BaseModel):
    id: str
    kb_id: str
    conversation_id: str | None
    title: str
    summary: str | None
    content_md: str
    raw_answer_md: str | None
    outline: list[str]
    citations: list[ReportCitationOut]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
