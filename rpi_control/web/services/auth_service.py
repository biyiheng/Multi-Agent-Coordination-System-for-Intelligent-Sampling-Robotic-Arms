"""Authentication service for the multi-end platform.

提供轻量、无外部依赖的 token 鉴权:
- 密码: PBKDF2-HMAC-SHA256 (hashlib 内置), 随机盐
- Token: secrets.token_hex(32), 库中仅存 SHA-256 哈希
- 依赖注入: get_current_user (Bearer / X-API-Key)

多端 (App / Web / 小程序) 共享同一套账号体系。
"""

import hashlib
import hmac
import logging
import secrets
import uuid
from typing import Any, Dict, Optional

from fastapi import Depends, Header, HTTPException, status

from rpi_control.database.repository import (
    db_manager, UserRepository, AuthTokenRepository,
)

logger = logging.getLogger(__name__)

_ITERATIONS = 100_000
_TOKEN_TTL_SECONDS = 7 * 24 * 3600  # 7 days


def hash_password(password: str, salt: Optional[str] = None) -> str:
    """Hash a password with a random salt (PBKDF2-HMAC-SHA256).

    Returns:
        "pbkdf2$<iterations>$<salt>$<digest>"
    """
    salt = salt or secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), _ITERATIONS
    ).hex()
    return f"pbkdf2${_ITERATIONS}${salt}${digest}"


def verify_password(password: str, stored: str) -> bool:
    """Verify a password against a stored pbkdf2 hash."""
    try:
        _, iterations, salt, digest = stored.split("$")
        test = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
        ).hex()
        return hmac.compare_digest(test, digest)
    except (ValueError, TypeError):
        return False


def issue_token(user_id: str, scope: str = "app") -> str:
    """Generate a new access token and persist only its hash."""
    token = secrets.token_hex(32)
    with db_manager.get_session() as session:
        AuthTokenRepository.create(
            session, user_id=user_id, token_hash=_hash_token(token), scope=scope
        )
    logger.info(f"Issued token for user {user_id} (scope={scope})")
    return token


def revoke_tokens(user_id: str) -> None:
    """Revoke all tokens for a user."""
    with db_manager.get_session() as session:
        AuthTokenRepository.delete_user_tokens(session, user_id)


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def register_user(username: str, password: str, role: str = "user") -> Dict[str, Any]:
    """Register a new platform user.

    Raises:
        ValueError: If the username already exists.
    """
    with db_manager.get_session() as session:
        if UserRepository.get_by_username(session, username):
            raise ValueError(f"用户名已存在: {username}")
        user = UserRepository.create(
            session,
            user_id=str(uuid.uuid4()),
            username=username,
            password_hash=hash_password(password),
            role=role,
        )
        return {"id": user.id, "username": user.username, "role": user.role,
                "enabled": bool(user.enabled)}


def authenticate(username: str, password: str) -> Optional[Dict[str, Any]]:
    """Authenticate a user; returns user dict or None."""
    with db_manager.get_session() as session:
        user = UserRepository.get_by_username(session, username)
        if not user or not user.enabled:
            return None
        if not verify_password(password, user.password_hash):
            return None
        return {"id": user.id, "username": user.username, "role": user.role,
                "enabled": bool(user.enabled)}


def get_current_user(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
) -> Dict[str, Any]:
    """FastAPI dependency: resolve the current user from a Bearer/API-Key token.

    Raises:
        HTTPException(401): If no/invalid token.
    """
    token: Optional[str] = None
    if authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    elif x_api_key:
        token = x_api_key.strip()

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="未提供访问令牌 (Authorization: Bearer <token> 或 X-API-Key)",
        )

    token_hash = _hash_token(token)
    with db_manager.get_session() as session:
        record = AuthTokenRepository.get_by_hash(session, token_hash)
        if not record:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效或已过期的访问令牌",
            )
        user = UserRepository.get(session, record.user_id)
        if not user or not user.enabled:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户不存在或已禁用",
            )
        return {"id": user.id, "username": user.username, "role": user.role,
                "enabled": bool(user.enabled)}


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    """Dependency: require the 'admin' role."""
    if current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="需要管理员权限",
        )
    return current_user
