from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseOut, KnowledgeBaseUpdate
from app.schemas.search import SearchHitOut, SearchResultOut
from app.services import knowledge_base_service as kb_service
from app.services import search_service as search_svc

router = APIRouter()


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = await kb_service.list_knowledge_bases(session, user_id)
    return [KnowledgeBaseOut.model_validate(r) for r in rows]


@router.get("/{kb_id}/search", response_model=SearchResultOut)
async def search_knowledge_base(
    kb_id: str,
    q: str = Query(..., min_length=1, max_length=2000),
    limit: int = Query(default=20, ge=1, le=50),
    category_id: str | None = Query(default=None),
    tags: str | None = Query(default=None, description="逗号分隔标签"),
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    tag_list = [t.strip() for t in (tags or "").split(",") if t.strip()]
    try:
        hits = await search_svc.hybrid_search(
            session,
            user_id,
            kb_id,
            q,
            limit=limit,
            category_id=category_id,
            tags=tag_list or None,
        )
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    except search_svc.SearchError as e:
        raise HTTPException(e.status_code, detail=e.message) from e

    items = [
        SearchHitOut(
            item_id=h.item_id,
            title=h.title,
            snippet=h.snippet,
            score=round(h.score, 4),
            source_type=h.source_type,
            page=h.page,
            tags=h.tags,
        )
        for h in hits
    ]
    return SearchResultOut(query=q.strip(), total=len(items), items=items)


@router.post("", response_model=KnowledgeBaseOut, status_code=status.HTTP_201_CREATED)
async def create_knowledge_base(
    body: KnowledgeBaseCreate,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        kb = await kb_service.create_knowledge_base(session, user_id, body.name)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return KnowledgeBaseOut.model_validate(kb)


@router.patch("/{kb_id}", response_model=KnowledgeBaseOut)
async def update_knowledge_base(
    kb_id: str,
    body: KnowledgeBaseUpdate,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        kb = await kb_service.update_knowledge_base(session, user_id, kb_id, body.name)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return KnowledgeBaseOut.model_validate(kb)


@router.delete("/{kb_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_knowledge_base(
    kb_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        await kb_service.delete_knowledge_base(session, user_id, kb_id)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)
