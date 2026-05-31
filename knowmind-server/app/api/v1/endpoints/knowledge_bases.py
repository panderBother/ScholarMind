from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.core.config import settings
from app.db.session import get_db
from app.schemas.knowledge_base import KnowledgeBaseCreate, KnowledgeBaseOut, KnowledgeBaseUpdate
from app.schemas.search import SearchHitOut, SearchResultOut
from app.schemas.skill_export import SkillExportJson
from app.services import knowledge_base_service as kb_service
from app.services import search_service as search_svc
from app.services import skill_export_service as export_svc
from app.services import usage_analytics_service as usage_svc

router = APIRouter()


def _api_base_from_request(request: Request) -> str:
    if settings.public_api_base_url:
        return settings.public_api_base_url.rstrip("/")
    return str(request.base_url).rstrip("/") + settings.api_v1_prefix


@router.get("", response_model=list[KnowledgeBaseOut])
async def list_knowledge_bases(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = await kb_service.list_knowledge_bases(session, user_id)
    item_counts = await kb_service.count_items_by_kb_ids(session, [r.id for r in rows])
    return [
        KnowledgeBaseOut.model_validate(r).model_copy(
            update={"item_count": item_counts.get(r.id, 0)},
        )
        for r in rows
    ]


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

    if hits:
        await usage_svc.log_usage_safe(
            session,
            lambda: usage_svc.record_search_hits(
                session,
                user_id=user_id,
                kb_id=kb_id,
                hits=hits,
            ),
        )
        await session.commit()

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


@router.get("/{kb_id}/export/skill")
async def export_skill(
    kb_id: str,
    request: Request,
    format: str = Query(default="markdown", pattern="^(markdown|json)$"),
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        kb = await kb_service.get_knowledge_base(session, user_id, kb_id)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e

    api_base = _api_base_from_request(request)
    if format == "json":
        payload = export_svc.build_skill_json(kb=kb, api_base=api_base)
        return SkillExportJson.model_validate(payload)

    md = export_svc.build_skill_markdown(kb=kb, api_base=api_base)
    filename = export_svc.skill_markdown_filename(kb)
    return Response(
        content=md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{kb_id}/export/mcp-manifest")
async def export_mcp_manifest(
    kb_id: str,
    request: Request,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        kb = await kb_service.get_knowledge_base(session, user_id, kb_id)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e

    api_base = _api_base_from_request(request)
    mcp_root = settings.knowmind_mcp_root
    body = export_svc.mcp_manifest_json(kb=kb, api_base=api_base, mcp_root=mcp_root)
    filename = export_svc.mcp_manifest_filename(kb)
    return Response(
        content=body,
        media_type="application/json; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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
