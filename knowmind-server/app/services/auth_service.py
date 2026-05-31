from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
    hash_password,
    verify_password,
)
from app.models.orm import User, new_uuid
from app.schemas.auth import TokenResponse, UserPublic


class AuthError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


async def register_user(session: AsyncSession, email: str, password: str) -> tuple[UserPublic, TokenResponse]:
    email_norm = email.strip().lower()
    existing = await session.execute(select(User).where(User.email == email_norm))
    if existing.scalar_one_or_none() is not None:
        raise AuthError("EMAIL_TAKEN", "该邮箱已注册", 409)

    user = User(id=new_uuid(), email=email_norm, password_hash=hash_password(password))
    session.add(user)
    await session.commit()
    await session.refresh(user)

    token, expires_in = create_access_token(user.id)
    refresh, refresh_exp = create_refresh_token(user.id)
    return UserPublic.model_validate(user), TokenResponse(
        access_token=token,
        refresh_token=refresh,
        expires_in=expires_in,
        refresh_expires_in=refresh_exp,
    )


async def login_user(session: AsyncSession, email: str, password: str) -> tuple[UserPublic, TokenResponse]:
    email_norm = email.strip().lower()
    result = await session.execute(select(User).where(User.email == email_norm))
    user = result.scalar_one_or_none()
    if user is None or not verify_password(password, user.password_hash):
        raise AuthError("INVALID_CREDENTIALS", "邮箱或密码错误", 401)
    if not user.is_active:
        raise AuthError("USER_DISABLED", "账号未激活或已禁用", 403)

    token, expires_in = create_access_token(user.id)
    refresh, refresh_exp = create_refresh_token(user.id)
    return UserPublic.model_validate(user), TokenResponse(
        access_token=token,
        refresh_token=refresh,
        expires_in=expires_in,
        refresh_expires_in=refresh_exp,
    )


async def get_user_by_id(session: AsyncSession, user_id: str) -> User | None:
    return await session.get(User, user_id)


async def refresh_tokens(session: AsyncSession, refresh_token: str) -> TokenResponse:
    user_id = decode_refresh_token(refresh_token)
    if not user_id:
        raise AuthError("INVALID_REFRESH", "刷新令牌无效或已过期", 401)
    user = await get_user_by_id(session, user_id)
    if user is None or not user.is_active:
        raise AuthError("USER_DISABLED", "账号不可用", 403)
    access, expires_in = create_access_token(user.id)
    refresh, refresh_exp = create_refresh_token(user.id)
    return TokenResponse(
        access_token=access,
        refresh_token=refresh,
        expires_in=expires_in,
        refresh_expires_in=refresh_exp,
    )


async def change_password(
    session: AsyncSession,
    user_id: str,
    *,
    current_password: str,
    new_password: str,
) -> None:
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise AuthError("NOT_FOUND", "用户不存在", 404)
    if not verify_password(current_password, user.password_hash):
        raise AuthError("INVALID_PASSWORD", "当前密码错误", 400)
    user.password_hash = hash_password(new_password)
    await session.commit()
