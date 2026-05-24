from pydantic import BaseModel, Field


class FileReadRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)


class FileWriteRequest(BaseModel):
    path: str = Field(min_length=1, max_length=4096)
    content: str = Field(max_length=2_000_000)
    format: str = Field(default="auto", pattern="^(auto|markdown|text)$")
    overwrite: bool = True


class FileOpResponse(BaseModel):
    path: str | None = None
    content: str | None = None
    status: str
    truncated: bool | None = None
    bytes_written: int | None = None
    size_bytes: int | None = None
    detail: str | None = None


class AllowedRootsResponse(BaseModel):
    allowed_roots: list[str]
    hint_env: str
