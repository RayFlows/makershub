# app/core/security/tokens.py
"""
访问令牌工具

旧系统的 JWT subject 直接使用微信 openid。新系统已经明确“用户主体不等于 openid”，
所以这里统一把内部用户主键写入 sub，并通过额外 claim 标记登录渠道。

旧小程序曾经只判断本地是否存在 auth_token，导致后端令牌过期后客户端仍然认为
用户已经登录，最终只能手动清理缓存。新版签发令牌时必须同时返回明确的过期时间，
客户端启动时也必须通过 `/auth/me` 让后端确认令牌仍然有效。

主要功能:
1. 签发访问令牌和客户端可缓存的过期信息；
2. 校验访问令牌；
3. 将 JWT 相关异常转换为统一 AppError。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.shared.time import utc_now


@dataclass(frozen=True)
class AccessToken:
    """访问令牌签发结果。"""

    token: str
    expires_at: datetime
    expires_in: int


def issue_access_token(
    *,
    subject: int | str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> AccessToken:
    """
    签发访问令牌。

    Args:
        subject: 内部用户主体 ID，会写入 JWT 的 sub 字段。
        extra_claims: 附加声明，例如登录渠道。
        expires_delta: 自定义有效期，主要用于测试过期令牌。

    Returns:
        访问令牌及其过期信息。
    """

    settings = get_settings()
    now = utc_now()
    if expires_delta is None:
        lifetime = timedelta(minutes=settings.access_token_expire_minutes)
    else:
        lifetime = expires_delta
    expires_at = now + lifetime
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": expires_at,
    }
    if extra_claims:
        payload.update(extra_claims)

    token = jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)
    expires_in = max(0, int((expires_at - now).total_seconds()))
    return AccessToken(token=token, expires_at=expires_at, expires_in=expires_in)


def create_access_token(
    *,
    subject: int | str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    创建访问令牌字符串。

    这个函数保留给只需要 JWT 字符串的内部调用。HTTP 登录接口应优先使用
    issue_access_token，把 expires_at 一并返回给客户端。
    """

    return issue_access_token(subject=subject, extra_claims=extra_claims).token


def decode_access_token(token: str) -> dict[str, Any]:
    """
    解码并校验访问令牌。

    Args:
        token: Authorization Bearer 中的 JWT 字符串。

    Returns:
        JWT payload。

    Raises:
        AppError: token 无效、过期或类型不匹配时抛出。
    """

    settings = get_settings()
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret_key,
            algorithms=[settings.jwt_algorithm],
        )
    except ExpiredSignatureError as exc:
        raise AppError("ACCESS_TOKEN_EXPIRED", "访问令牌已过期", status_code=401) from exc
    except InvalidTokenError as exc:
        raise AppError("INVALID_ACCESS_TOKEN", "访问令牌无效", status_code=401) from exc

    if payload.get("type") != "access":
        raise AppError("INVALID_TOKEN_TYPE", "访问令牌类型不正确", status_code=401)

    if not payload.get("sub"):
        raise AppError("INVALID_ACCESS_TOKEN", "访问令牌缺少用户标识", status_code=401)

    return payload
