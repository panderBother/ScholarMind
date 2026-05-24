from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from fastapi.responses import PlainTextResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.report import (
    ResearchReportListItem,
    ResearchReportOut,
)
from app.services import report_service as report_svc
from app.services.report_service import ReportError
from app.utils.http_headers import attachment_content_disposition

router = APIRouter()


def _list_item(row) -> ResearchReportListItem:
    citations = row.citations_json if isinstance(row.citations_json, list) else []
    return ResearchReportListItem(
        id=row.id,
        kb_id=row.kb_id,
        conversation_id=row.conversation_id,
        title=row.title,
        summary=row.summary,
        status=row.status,
        citation_count=len(citations),
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _detail(row) -> ResearchReportOut:
    return report_svc.report_to_schema(row)


@router.get("", response_model=list[ResearchReportListItem])
async def list_reports(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    kb_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
):
    rows = await report_svc.list_reports(session, user_id, kb_id=kb_id, limit=limit)
    return [_list_item(r) for r in rows]


@router.get("/{report_id}", response_model=ResearchReportOut)
async def get_report(
    report_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        row = await report_svc.get_report(session, user_id, report_id)
    except ReportError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return _detail(row)


@router.delete("/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_report(
    report_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        await report_svc.delete_report(session, user_id, report_id)
    except ReportError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{report_id}/export")
async def export_report_markdown(
    report_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    try:
        row = await report_svc.get_report(session, user_id, report_id)
    except ReportError as e:
        raise HTTPException(e.status_code, detail=e.message) from e
    body = f"# {row.title}\n\n"
    if row.summary:
        body += f"> {row.summary}\n\n"
    body += report_svc.finalize_report_markdown(row.content_md or "")
    citations = row.citations_json if isinstance(row.citations_json, list) else []
    if citations:
        body += "\n\n## 引用来源\n\n"
        for c in citations:
            idx = c.get("index", "?")
            title = c.get("title", "")
            meta = c.get("meta") or ""
            body += f"- [^{idx}] **{title}** {meta}\n"
    headers = {"Content-Disposition": attachment_content_disposition(row.title)}
    return PlainTextResponse(content=body, media_type="text/markdown; charset=utf-8", headers=headers)
