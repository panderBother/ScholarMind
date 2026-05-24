from pydantic import BaseModel, Field


class SearchHitOut(BaseModel):
    item_id: str
    title: str
    snippet: str
    score: float
    source_type: str
    page: int | None = None
    tags: list[str] = Field(default_factory=list)


class SearchResultOut(BaseModel):
    query: str
    total: int
    items: list[SearchHitOut]
