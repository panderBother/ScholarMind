from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseOut
from app.services import knowledge_base_service as kb_service

router = APIRouter()


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = await kb_service.list_knowledge_bases(session, user_id)
    return [KnowledgeBaseOut.model_validate(r) for r in rows]


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
