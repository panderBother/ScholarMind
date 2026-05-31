from datetime import datetime

from pydantic import BaseModel, Field


class ConversationCreate(BaseModel):
    knowledge_base_id: str | None = None
    deep_research: bool = False
    web_search: bool = False
    title: str | None = Field(default=None, max_length=255)


class ConversationUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class ConversationOut(BaseModel):
    id: str
    knowledge_base_id: str | None
    expert_id: str | None = None
    deep_research: bool
    web_search: bool
    title: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ChatMessageOut(BaseModel):
    id: str
    role: str
    content: str
    trace_id: str | None
    created_at: datetime

    model_config = {"from_attributes": True}
