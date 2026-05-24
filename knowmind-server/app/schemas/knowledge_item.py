from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeItemCreate(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    category_id: str
    summary: str | None = Field(default=None, max_length=500)
    tags: list[str] = Field(default_factory=list)
    access_level: str = Field(default="internal", pattern="^(public|internal|restricted)$")
    source: str | None = Field(default=None, max_length=512)
    publish: bool = False


class KnowledgeItemUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=200)
    content: str | None = Field(default=None, min_length=1)
    category_id: str | None = None
    summary: str | None = Field(default=None, max_length=500)
    tags: list[str] | None = None
    access_level: str | None = Field(default=None, pattern="^(public|internal|restricted)$")
    source: str | None = Field(default=None, max_length=512)


class KnowledgeItemOut(BaseModel):
    id: str
    kb_id: str
    document_id: str | None
    category_id: str | None
    source_type: str
    title: str
    content: str
    summary: str | None
    tags: list[str] | None
    lifecycle_status: str
    access_level: str
    source: str | None
    chunk_id: str | None
    page: int | None
    published_at: datetime | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class UrlImportRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)
    category_id: str
    publish: bool = False
    # 预览确认后传入，避免重复抓取/蒸馏
    title: str | None = Field(default=None, max_length=200)
    content: str | None = None
    summary: str | None = Field(default=None, max_length=500)


class UrlPreviewRequest(BaseModel):
    url: str = Field(min_length=8, max_length=2048)


class UrlImportPreviewOut(BaseModel):
    url: str
    page_title: str | None
    title: str
    summary: str | None
    content: str


class ImportDraftItem(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    tags: list[str] = Field(default_factory=list)


class ImportDraftsRequest(BaseModel):
    drafts: list[ImportDraftItem]
    publish: bool = False


class KnowledgeGapOut(BaseModel):
    id: str
    kb_id: str
    gap_key: str
    trigger_rule: str
    sample_queries: list[str]
    avg_score: float | None
    hit_count: int
    status: str
    draft_item_ids: list[str] | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatFeedbackRequest(BaseModel):
    knowledge_base_id: str | None = None
    conversation_id: str | None = None
    message_id: str | None = None
    query_text: str | None = None
    correction: str = Field(min_length=1, max_length=8000)


class ExtractKnowledgeRequest(BaseModel):
    kb_id: str
    message_limit: int = Field(default=8, ge=2, le=20)
