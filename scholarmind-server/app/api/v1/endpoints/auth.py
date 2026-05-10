from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user_id
from app.db.session import get_db
from app.schemas.auth import AuthOkResponse, LoginRequest, RegisterRequest, UserPublic
from app.services import auth_service

router = APIRouter()


@router.post("/register", response_model=AuthOkResponse)
async def register(body: RegisterRequest, session: AsyncSession = Depends(get_db)):
    try:
        user, tok = await auth_service.register_user(session, body.email, body.password)
    except auth_service.AuthError as e:
        raise HTTPException(e.status_code, detail={"code": e.code, "message": e.message}) from e
    return AuthOkResponse(
        user=user,
        access_token=tok.access_token,
        token_type=tok.token_type,
        expires_in=tok.expires_in,
    )


@router.post("/login", response_model=AuthOkResponse)
async def login(body: LoginRequest, session: AsyncSession = Depends(get_db)):
    try:
        user, tok = await auth_service.login_user(session, body.email, body.password)
    except auth_service.AuthError as e:
        raise HTTPException(e.status_code, detail={"code": e.code, "message": e.message}) from e
    return AuthOkResponse(
        user=user,
        access_token=tok.access_token,
        token_type=tok.token_type,
        expires_in=tok.expires_in,
    )


@router.get("/me", response_model=UserPublic)
async def me(
    session: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
):
    user = await auth_service.get_user_by_id(session, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "用户不存在")
    return UserPublic.model_validate(user)
