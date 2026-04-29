# app/core/security/tokens.py
"""
访问令牌工具

旧系统的 JWT subject 直接使用微信 openid。新系统已经明确“用户主体不等于 openid”，
所以这里统一把内部用户主键写入 sub，并通过额外 claim 标记登录渠道。

主要功能:
1. 签发访问令牌；
2. 校验访问令牌；
3. 将 JWT 相关异常转换为统一 AppError。
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt

from app.core.config.settings import get_settings
from app.core.errors import AppError


def create_access_token(
    *,
    subject: int | str,
    extra_claims: dict[str, Any] | None = None,
) -> str:
    """
    创建访问令牌。

    Args:
        subject: 内部用户主体 ID，会写入 JWT 的 sub 字段。
        extra_claims: 附加声明，例如登录渠道。

    Returns:
        编码后的 JWT 字符串。
    """

    settings = get_settings()
    now = datetime.now(UTC)
    expire = now + timedelta(minutes=settings.access_token_expire_minutes)
    payload: dict[str, Any] = {
        "sub": str(subject),
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": expire,
    }
    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


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
    except JWTError as exc:
        raise AppError("INVALID_ACCESS_TOKEN", "访问令牌无效或已过期", status_code=401) from exc

    if payload.get("type") != "access":
        raise AppError("INVALID_TOKEN_TYPE", "访问令牌类型不正确", status_code=401)

    if not payload.get("sub"):
        raise AppError("INVALID_ACCESS_TOKEN", "访问令牌缺少用户标识", status_code=401)

    return payload
