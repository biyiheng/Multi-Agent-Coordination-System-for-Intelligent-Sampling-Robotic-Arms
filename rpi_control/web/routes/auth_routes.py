"""Authentication & user management API routes (multi-end platform).

多端 (App / Web / 小程序) 共享同一套账号体系:

- POST /api/v1/auth/register  注册
- POST /api/v1/auth/login     登录 (签发 token)
- POST /api/v1/auth/logout    注销 (吊销当前用户 token)
- GET  /api/v1/auth/me        当前用户信息
- GET  /api/v1/auth/users     用户列表 (管理员)
- PUT  /api/v1/auth/users/{id}   更新用户 (管理员: 角色/禁用/改密)
- DELETE /api/v1/auth/users/{id} 删除用户 (管理员)
"""

import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from rpi_control.database.repository import UserRepository, db_manager
from rpi_control.web.models.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserInfo,
)
from rpi_control.web.services import auth_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/register", response_model=TokenResponse)
async def register(req: RegisterRequest):
    """Register a new platform user and return an access token."""
    try:
        user = auth_service.register_user(req.username, req.password, role=req.role)
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e))

    token = auth_service.issue_token(user["id"], scope=req.role or "app")
    return TokenResponse(access_token=token, user=user)


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    """Authenticate and issue an access token."""
    user = auth_service.authenticate(req.username, req.password)
    if not user:
        raise HTTPException(
            status_code=401,
            detail="用户名或密码错误",
        )
    token = auth_service.issue_token(user["id"], scope=req.scope)
    return TokenResponse(access_token=token, user=user)


@router.post("/logout")
async def logout(current_user: Dict[str, Any] = Depends(auth_service.get_current_user)):
    """Revoke all tokens for the current user."""
    auth_service.revoke_tokens(current_user["id"])
    return {"status": "ok", "message": "已注销登录"}


@router.get("/me", response_model=UserInfo)
async def me(current_user: Dict[str, Any] = Depends(auth_service.get_current_user)):
    """Return the currently authenticated user's info."""
    return UserInfo(
        id=current_user["id"],
        username=current_user["username"],
        role=current_user["role"],
        enabled=bool(current_user["enabled"]),
    )


# ---------------------------------------------------------------------------
# 用户管理 (仅管理员)
# ---------------------------------------------------------------------------


def _user_to_dict(user) -> Dict[str, Any]:
    return {
        "id": user.id,
        "username": user.username,
        "role": user.role,
        "enabled": bool(user.enabled),
        "created_at": user.created_at.isoformat() if user.created_at else None,
        "updated_at": user.updated_at.isoformat() if user.updated_at else None,
    }


@router.get("/users")
async def list_users(
    limit: int = 100,
    admin: Dict[str, Any] = Depends(auth_service.require_admin),
):
    """List all platform users (admin only)."""
    with db_manager.get_session() as session:
        users = UserRepository.list_all(session, limit=limit)
        return [_user_to_dict(u) for u in users]


@router.put("/users/{user_id}")
async def update_user(
    user_id: str,
    updates: Dict[str, Any],
    admin: Dict[str, Any] = Depends(auth_service.require_admin),
):
    """Update a user's role / enabled flag, or reset their password.

    Request body example:
      {"role": "viewer", "enabled": true}
      {"password": "new-password"}   -> 重置密码 (自动哈希)
    """
    if "password" in updates:
        updates["password_hash"] = auth_service.hash_password(updates["password"])
        updates.pop("password")

    with db_manager.get_session() as session:
        user = UserRepository.update(session, user_id, updates)
        if not user:
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
        return _user_to_dict(user)


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    admin: Dict[str, Any] = Depends(auth_service.require_admin),
):
    """Delete a user and revoke their tokens (admin only)."""
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="不能删除当前登录的管理员账号")
    with db_manager.get_session() as session:
        if not UserRepository.delete(session, user_id):
            raise HTTPException(status_code=404, detail=f"用户不存在: {user_id}")
    logger.info(f"User deleted: {user_id}")
    return {"status": "ok", "message": f"用户 {user_id} 已删除"}
