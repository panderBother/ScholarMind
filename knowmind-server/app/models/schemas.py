from pydantic import BaseModel, Field, field_validator


class HealthResponse(BaseModel):
    status: str = Field(examples=["ok"])


class ChatRequest(BaseModel):
    """对话请求体：与前端 Chat 页对齐的最小字段集。"""

    message: str = Field(min_length=1, max_length=8000)
    knowledge_base_id: str | None = None
    deep_research: bool = False
    web_search: bool = False
    file_tools: bool = Field(
        default=False,
        description="启用本地文件读写工具（需服务端 file_tools_enabled）",
    )
    external_mcp: bool = Field(
        default=False,
        description="启用已配置的远程 URL 型外部 MCP 工具（需在工具页导入并开启）",
    )
    conversation_id: str | None = Field(
        default=None,
        description="不传或空则新建会话；传入已有 id 则续聊并写入 MySQL/Redis/向量索引",
    )

    @field_validator("conversation_id", mode="before")
    @classmethod
    def _empty_conv_id_none(cls, v: object) -> str | None:
        if v is None:
            return None
        if isinstance(v, str):
            s = v.strip()
            return s if s else None
        return str(v).strip()


class ChatResponse(BaseModel):
    reply: str
    trace_id: str
