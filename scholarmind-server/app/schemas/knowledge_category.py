from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeCategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    parent_id: str | None = None
    sort_order: int = 0


class KnowledgeCategoryUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    parent_id: str | None = None
    sort_order: int | None = None


class KnowledgeCategoryOut(BaseModel):
    id: str
    kb_id: str
    parent_id: str | None
    name: str
    sort_order: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class KnowledgeCategoryTreeNode(KnowledgeCategoryOut):
    children: list["KnowledgeCategoryTreeNode"] = Field(default_factory=list)


KnowledgeCategoryTreeNode.model_rebuild()
