from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeBaseCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class KnowledgeBaseUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=50)


class KnowledgeBaseOut(BaseModel):
    id: str
    name: str
    doc_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
