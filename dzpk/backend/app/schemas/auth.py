"""认证相关 Pydantic Schema。"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class GuestRequest(BaseModel):
    device_id: str = Field(..., min_length=1, max_length=64)


class GuestResponse(BaseModel):
    user_id: str
    token: str
    chips: int


class UpgradeRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=20, pattern=r"^[a-zA-Z0-9_\u4e00-\u9fa5]+$")
    password: str = Field(..., min_length=6, max_length=64)


class LoginRequest(BaseModel):
    username: str
    password: str


class UserInfo(BaseModel):
    id: str
    username: Optional[str] = None
    chips: int
    is_anonymous: bool
    total_hands: int
    total_wins: int
    total_profit: int
    created_at: datetime
    last_login_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    token: str
    user: UserInfo


class AuthSuccessResponse(BaseModel):
    success: bool
    user: UserInfo
