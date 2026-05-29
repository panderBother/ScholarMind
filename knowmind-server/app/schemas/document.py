from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    kb_id: str
    filename: str
    file_type: str | None = None
    status: str
    chunk_count: int
    file_bytes: int
    md5: str | None
    title: str | None
    parsed_title: str | None = None
    parsed_summary: str | None = None
    parse_progress: int = 0
    parse_stage: str | None = None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentOut] = Field(default_factory=list)
    skipped_duplicates: int = 0
    needs_preview: list[str] = Field(default_factory=list, description="需预览确认的文档 ID")


class DocumentParsedContentOut(BaseModel):
    doc_id: str
    filename: str
    file_type: str | None
    title: str | None
    summary: str | None
    content: str
    status: str


class DocumentParsedContentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=512)
    summary: str | None = Field(default=None, max_length=500)
    content: str = Field(..., min_length=1, max_length=200_000)


class DocumentConfirmImportResponse(BaseModel):
    document: DocumentOut
