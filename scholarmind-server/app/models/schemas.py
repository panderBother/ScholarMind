from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class ChatRequest(BaseModel):
    """对话请求体：与前端 Chat 页对齐的最小字段集。"""

    message: str = Field(min_length=1, max_length=8000)
    knowledge_base_id: str | None = None
    deep_research: bool = False
    web_search: bool = False


class ChatResponse(BaseModel):
    reply: str
    trace_id: str
