"""认证 API：匿名账号、升级、登录、获取用户信息。"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
from fastapi import APIRouter, Depends, HTTPException, Header
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..db.models import User
from ..db.session import SessionLocal
from ..schemas.auth import (
    GuestRequest,
    GuestResponse,
    LoginRequest,
    TokenResponse,
    UpgradeRequest,
    UserInfo,
)

logger = logging.getLogger("dzpk")

JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dzpk-dev-secret-key-change-in-production")
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_DAYS = 30

router = APIRouter(prefix="/auth", tags=["auth"])


def create_token(user_id: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(days=JWT_EXPIRE_DAYS)
    payload = {"sub": user_id, "exp": expire}
    return jwt.encode(payload, JWT_SECRET_KEY, algorithm=JWT_ALGORITHM)


def verify_token(token: str) -> str | None:
    """验证 JWT，成功返回 user_id，失败返回 None。"""
    try:
        payload = jwt.decode(token, JWT_SECRET_KEY, algorithms=[JWT_ALGORITHM])
        return payload.get("sub")
    except JWTError:
        return None


async def get_current_user(
    authorization: str = Header(..., description="Bearer <token>"),
) -> User:
    """从 Authorization header 解析 JWT 并返回 User。"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(401, "无效的认证头")
    token = authorization[7:]
    user_id = verify_token(token)
    if user_id is None:
        raise HTTPException(401, "Token 无效或已过期")

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            raise HTTPException(401, "用户不存在")
        return user


def _user_to_info(user: User) -> UserInfo:
    return UserInfo(
        id=user.id,
        username=user.username,
        chips=user.chips,
        is_anonymous=user.is_anonymous,
        total_hands=user.total_hands,
        total_wins=user.total_wins,
        total_profit=user.total_profit,
        created_at=user.created_at,
        last_login_at=user.last_login_at,
    )


@router.post("/guest", response_model=GuestResponse)
async def create_guest(req: GuestRequest) -> GuestResponse:
    """创建匿名账号或返回已有账号。"""
    async with SessionLocal() as db:
        # 查找同一 device_id 的匿名账号
        result = await db.execute(
            select(User).where(User.device_id == req.device_id, User.is_anonymous == True)
        )
        user = result.scalar_one_or_none()

        if user is None:
            user = User(
                id=str(uuid.uuid4()),
                device_id=req.device_id,
                chips=10000,
                is_anonymous=True,
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)
            logger.info("创建匿名账号: %s (device=%s)", user.id, req.device_id)
        else:
            user.last_login_at = datetime.now()
            await db.commit()
            logger.info("复用匿名账号: %s (device=%s)", user.id, req.device_id)

        token = create_token(user.id)
        return GuestResponse(user_id=user.id, token=token, chips=user.chips)


@router.post("/upgrade", response_model=TokenResponse)
async def upgrade_account(
    req: UpgradeRequest,
    user: User = Depends(get_current_user),
) -> TokenResponse:
    """将匿名账号升级为正式账号。"""
    if not user.is_anonymous:
        raise HTTPException(400, "当前账号已是正式账号，无需升级")

    async with SessionLocal() as db:
        # 检查用户名唯一性
        result = await db.execute(select(User).where(User.username == req.username))
        existing = result.scalar_one_or_none()
        if existing and existing.id != user.id:
            raise HTTPException(409, "用户名已被占用")

        # 更新用户
        user_attached = await db.get(User, user.id)
        if user_attached is None:
            raise HTTPException(404, "用户不存在")
        user_attached.username = req.username
        user_attached.password_hash = bcrypt.hashpw(
            req.password.encode("utf-8"), bcrypt.gensalt(rounds=12)
        ).decode("utf-8")
        user_attached.is_anonymous = False
        user_attached.last_login_at = datetime.now()
        await db.commit()
        await db.refresh(user_attached)

        token = create_token(user_attached.id)
        logger.info("账号升级: %s -> %s", user_attached.id, req.username)
        return TokenResponse(token=token, user=_user_to_info(user_attached))


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest) -> TokenResponse:
    """用户名密码登录。"""
    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.username == req.username))
        user = result.scalar_one_or_none()

        if user is None:
            raise HTTPException(401, "用户名或密码错误")
        if user.is_anonymous or not user.password_hash:
            raise HTTPException(401, "该账号未设置密码，请使用升级功能")

        if not bcrypt.checkpw(
            req.password.encode("utf-8"), user.password_hash.encode("utf-8")
        ):
            raise HTTPException(401, "用户名或密码错误")

        user.last_login_at = datetime.now()
        await db.commit()

        token = create_token(user.id)
        logger.info("用户登录: %s", user.username)
        return TokenResponse(token=token, user=_user_to_info(user))


@router.get("/me", response_model=UserInfo)
async def get_me(user: User = Depends(get_current_user)) -> UserInfo:
    """获取当前用户信息。"""
    return _user_to_info(user)
