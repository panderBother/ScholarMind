from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.document import DocumentOut, DocumentUploadResponse
from app.services import document_service

router = APIRouter()


@router.get("/{kb_id}/documents", response_model=list[DocumentOut])
async def list_documents(
    kb_id: str,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    rows = await document_service.list_documents(session, user_id, kb_id)
    return [DocumentOut.model_validate(r) for r in rows]


@router.post("/{kb_id}/documents", response_model=DocumentUploadResponse)
async def upload_documents(
    kb_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
    files: list[UploadFile] = File(...),
):
    if not files:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "请选择至少一个文件")
    return await document_service.upload_pdfs(session, user_id, kb_id, files, background_tasks)


@router.post("/{kb_id}/documents/{doc_id}/retry-parse", response_model=DocumentOut)
async def retry_parse_document(
    kb_id: str,
    doc_id: str,
    background_tasks: BackgroundTasks,
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    return await document_service.retry_document_parse(session, user_id, kb_id, doc_id, background_tasks)
