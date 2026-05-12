# app/modules/identity/sessions/service.py
"""
登录会话服务

本文件负责短期 access token、长期 refresh token、服务端会话轮换和会话撤销。
refresh token 只保存哈希值，退出登录或后台撤销后，旧 access token 也必须被拒绝。
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.core.security import issue_access_token
from app.modules.identity.models import AuthSession, User
from app.modules.identity.repositories import IdentityRepository
from app.modules.identity.types import AuthTokenPair
from app.modules.identity.utils import ensure_aware_datetime, trim_optional_text
from app.shared.time import utc_now


async def issue_auth_token_pair(
    session: AsyncSession,
    *,
    user: User,
    channel: str,
    client_type: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthTokenPair:
    """签发 access token + refresh token。

    access token 是短期 JWT，负责接口访问；refresh token 是长期随机凭证，
    只以哈希形式保存到 auth_sessions，用于续签和撤销。
    """

    normalized_channel = normalize_session_label(channel, field_name="channel")
    normalized_client_type = normalize_session_label(client_type, field_name="client_type")
    settings = get_settings()
    refresh_token = generate_refresh_token()
    refresh_expires_at = utc_now() + timedelta(days=settings.refresh_token_expire_days)

    repository = IdentityRepository(session)
    auth_session = await repository.create_auth_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        channel=normalized_channel,
        client_type=normalized_client_type,
        expires_at=refresh_expires_at,
        user_agent=trim_optional_text(user_agent, max_length=512),
        ip_address=trim_optional_text(ip_address, max_length=64),
    )
    access_token = issue_access_token(
        subject=user.id,
        extra_claims={
            "channel": normalized_channel,
            "sid": auth_session.id,
        },
    )
    return AuthTokenPair(
        user=user,
        auth_session=auth_session,
        access_token=access_token,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


async def refresh_auth_token_pair(
    session: AsyncSession,
    *,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthTokenPair:
    """使用 refresh token 续签令牌对。

    每次续签都会轮换 refresh token，旧 refresh token 立即失效。
    这样即使旧 token 泄露，也能在下一次合法续签后降低继续使用的窗口。
    """

    repository = IdentityRepository(session)
    auth_session = await repository.get_auth_session_by_refresh_hash(hash_refresh_token(refresh_token))
    if auth_session is None:
        raise AppError("INVALID_REFRESH_TOKEN", "刷新令牌无效", status_code=401)

    ensure_auth_session_usable(auth_session)
    user = await repository.get_user_by_id(auth_session.user_id)
    if user is None:
        raise AppError("AUTH_USER_NOT_FOUND", "登录用户不存在", status_code=401)
    if user.status != "active":
        raise AppError("AUTH_USER_DISABLED", "用户状态不可用", status_code=403)

    settings = get_settings()
    next_refresh_token = generate_refresh_token()
    refresh_expires_at = utc_now() + timedelta(days=settings.refresh_token_expire_days)
    await repository.rotate_auth_session(
        auth_session,
        refresh_token_hash=hash_refresh_token(next_refresh_token),
        expires_at=refresh_expires_at,
        user_agent=trim_optional_text(user_agent, max_length=512),
        ip_address=trim_optional_text(ip_address, max_length=64),
    )
    access_token = issue_access_token(
        subject=user.id,
        extra_claims={
            "channel": auth_session.channel,
            "sid": auth_session.id,
        },
    )
    return AuthTokenPair(
        user=user,
        auth_session=auth_session,
        access_token=access_token,
        refresh_token=next_refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


async def revoke_auth_token_pair(
    session: AsyncSession,
    *,
    refresh_token: str,
    reason: str = "logout",
) -> AuthSession:
    """撤销 refresh token 对应的登录会话。"""

    repository = IdentityRepository(session)
    auth_session = await repository.get_auth_session_by_refresh_hash(hash_refresh_token(refresh_token))
    if auth_session is None:
        raise AppError("INVALID_REFRESH_TOKEN", "刷新令牌无效", status_code=401)

    if auth_session.status == "revoked":
        return auth_session

    await repository.revoke_auth_session(auth_session, reason=reason)
    return auth_session


async def validate_auth_session(
    session: AsyncSession,
    *,
    auth_session_id: int,
) -> AuthSession:
    """校验 access token 中携带的会话是否仍然有效。"""

    repository = IdentityRepository(session)
    auth_session = await repository.get_auth_session_by_id(auth_session_id)
    if auth_session is None:
        raise AppError("AUTH_SESSION_NOT_FOUND", "登录会话不存在", status_code=401)
    ensure_auth_session_usable(auth_session)
    return auth_session


def generate_refresh_token() -> str:
    """生成高熵 refresh token。"""

    return secrets.token_urlsafe(48)


def hash_refresh_token(refresh_token: str) -> str:
    """计算 refresh token 哈希，避免数据库保存明文长期凭证。"""

    normalized = refresh_token.strip()
    if not normalized:
        raise AppError("REFRESH_TOKEN_REQUIRED", "缺少刷新令牌", status_code=422)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_session_label(value: str, *, field_name: str) -> str:
    """规范化会话来源标签。"""

    normalized = value.strip().lower()
    if not normalized:
        raise AppError("INVALID_AUTH_SESSION_LABEL", f"{field_name} 不能为空", status_code=422)
    return normalized


def ensure_auth_session_usable(auth_session: AuthSession) -> None:
    """确认登录会话仍处于可使用状态。"""

    if auth_session.status == "revoked" or auth_session.revoked_at is not None:
        raise AppError("AUTH_SESSION_REVOKED", "登录会话已失效", status_code=401)
    if auth_session.status != "active":
        raise AppError("AUTH_SESSION_DISABLED", "登录会话不可用", status_code=401)
    if ensure_aware_datetime(auth_session.expires_at) <= utc_now():
        raise AppError("REFRESH_TOKEN_EXPIRED", "刷新令牌已过期", status_code=401)
