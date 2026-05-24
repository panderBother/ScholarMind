from datetime import datetime

from pydantic import BaseModel, Field


class DocumentOut(BaseModel):
    id: str
    kb_id: str
    filename: str
    status: str
    chunk_count: int
    file_bytes: int
    md5: str | None
    title: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class DocumentUploadResponse(BaseModel):
    documents: list[DocumentOut] = Field(default_factory=list)
    skipped_duplicates: int = 0
