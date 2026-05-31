from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserPublic(BaseModel):
    id: str
    email: EmailStr
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int  # seconds
    refresh_expires_in: int | None = None


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=10)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=8, max_length=128)


class AuthOkResponse(BaseModel):
    """注册/登录统一返回：用户信息 + JWT。"""

    user: UserPublic
    access_token: str
    refresh_token: str | None = None
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int | None = None
