from typing import Any

from pydantic import BaseModel, Field


class SkillExportJson(BaseModel):
    name: str = "search_kb"
    description: str
    parameters: dict[str, Any]
    kb_id: str
    kb_name: str
    api_base: str
    endpoint: str
    auth: str = Field(default="Authorization: Bearer <access_token>")
