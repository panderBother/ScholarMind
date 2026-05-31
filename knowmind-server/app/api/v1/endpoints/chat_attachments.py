"""对话附件上传 API。"""

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import get_current_user_id
from app.services import chat_attachment_service as att_svc

router = APIRouter()


@router.post("")
async def upload_chat_attachment(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user_id),
):
    data = await file.read()
    if not data:
        raise HTTPException(400, "空文件")
    try:
        return await att_svc.save_attachment(user_id, file.filename or "upload.bin", data)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
