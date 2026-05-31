from pydantic import BaseModel, Field


class McpServerConfig(BaseModel):
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    env: dict[str, str] = Field(default_factory=dict)
    headers: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    cwd: str | None = None


class BuiltinMcpToolDto(BaseModel):
    id: str
    name: str
    description: str
    enabled: bool
    available: bool = True
    kind: str = "builtin"


class CustomMcpToolDto(BaseModel):
    id: str
    name: str
    description: str = ""
    enabled: bool
    source: str = "import"
    config: McpServerConfig
    imported_at: str


class McpToolsResponse(BaseModel):
    builtin: list[BuiltinMcpToolDto]
    custom: list[CustomMcpToolDto]


class UpdateBuiltinMcpRequest(BaseModel):
    id: str
    enabled: bool


class UpdateCustomMcpRequest(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = Field(default="", max_length=500)
    enabled: bool = True
    config: McpServerConfig


class ImportMcpRequest(BaseModel):
    """Cursor / Claude Desktop 风格 mcp.json 全文或 mcpServers 对象。"""

    raw_json: str = Field(min_length=2, max_length=200_000)


class ImportMcpResponse(BaseModel):
    imported: int
    skipped: int
    skip_details: list[str] = Field(default_factory=list)
    custom: list[CustomMcpToolDto]
