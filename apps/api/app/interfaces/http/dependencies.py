# app/interfaces/http/dependencies.py
"""
HTTP 依赖项

这里放接口层通用依赖，例如当前登录用户解析。
依赖项只处理协议相关内容，业务权限判断后续会下沉到权限模块。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Header
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import AppError
from app.core.security import decode_access_token
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository


@dataclass(frozen=True)
class CurrentUser:
    """当前登录用户上下文。"""

    user: User
    claims: dict[str, Any]


async def get_current_user(
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """
    从 Authorization 请求头解析当前用户。

    Args:
        authorization: Bearer token 请求头。
        session: 当前请求数据库会话。

    Returns:
        当前用户和 JWT claims。

    Raises:
        AppError: 未登录、token 无效或用户不存在时抛出。
    """

    if not authorization:
        raise AppError("AUTH_HEADER_MISSING", "缺少 Authorization 请求头", status_code=401)

    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise AppError("AUTH_HEADER_INVALID", "Authorization 格式应为 Bearer token", status_code=401)

    claims = decode_access_token(token)
    try:
        user_id = int(claims["sub"])
    except (TypeError, ValueError) as exc:
        raise AppError("INVALID_ACCESS_TOKEN", "访问令牌用户标识不合法", status_code=401) from exc

    repository = IdentityRepository(session)
    user = await repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("AUTH_USER_NOT_FOUND", "登录用户不存在", status_code=401)
    if user.status != "active":
        raise AppError("AUTH_USER_DISABLED", "用户状态不可用", status_code=403)

    return CurrentUser(user=user, claims=claims)
