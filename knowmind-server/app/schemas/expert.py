from datetime import datetime

from pydantic import BaseModel, Field


class ExpertCreateIn(BaseModel):
    kb_id: str = Field(min_length=1, max_length=36)
    name: str | None = Field(default=None, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ExpertOut(BaseModel):
    id: str
    kb_id: str
    name: str
    description: str | None
    system_prompt: str
    created_at: datetime
    updated_at: datetime


class ExpertChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=8000)
    deep_research: bool = False
    conversation_id: str | None = None

    @classmethod
    def _empty_conv_id_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v).strip()
