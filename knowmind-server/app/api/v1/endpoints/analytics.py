from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.analytics import (
    AnalyticsOverviewOut,
    AnalyticsTrendOut,
    TopItemsOut,
)
from app.services import knowledge_base_service as kb_service
from app.services import usage_analytics_service as analytics_svc

router = APIRouter()


@router.get("/{kb_id}/analytics/overview", response_model=AnalyticsOverviewOut)
async def analytics_overview(
    kb_id: str,
    days: int = Query(default=7, ge=7, le=30),
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        data = await analytics_svc.get_overview(session, user_id, kb_id, days=days)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return AnalyticsOverviewOut.model_validate(data)


@router.get("/{kb_id}/analytics/top-items", response_model=TopItemsOut)
async def analytics_top_items(
    kb_id: str,
    days: int = Query(default=7, ge=7, le=30),
    limit: int = Query(default=10, ge=1, le=50),
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        items = await analytics_svc.get_top_items(
            session,
            user_id,
            kb_id,
            days=days,
            limit=limit,
        )
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return TopItemsOut(items=items)


@router.get("/{kb_id}/analytics/trend", response_model=AnalyticsTrendOut)
async def analytics_trend(
    kb_id: str,
    days: int = Query(default=7, ge=7, le=30),
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        data = await analytics_svc.get_trend(session, user_id, kb_id, days=days)
    except kb_service.KnowledgeBaseError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return AnalyticsTrendOut.model_validate(data)
