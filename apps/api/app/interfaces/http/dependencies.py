# app/interfaces/http/dependencies.py
"""
HTTP 依赖项

这里放接口层通用依赖，例如当前登录用户解析和权限依赖。
依赖项只处理 HTTP 协议、FastAPI 安全声明和错误转换；权限判断本身由
core.permissions 服务层负责。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated, Any

from fastapi import Depends, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import AppError
from app.core.logging import logger
from app.core.permissions.service import check_user_permission
from app.core.security import decode_access_token
from app.core.security.middleware import get_client_ip
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.identity.models import User
from app.modules.identity.repository import IdentityRepository
from app.modules.identity.service import validate_auth_session
from app.shared.request_context import get_request_id

bearer_scheme = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class CurrentUser:
    """当前登录用户上下文。"""

    user: User
    claims: dict[str, Any]


async def resolve_current_user_from_authorization(
    *,
    authorization: str | None,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """
    从 Authorization 字符串解析当前用户。

    Args:
        authorization: Bearer token 请求头原始值。
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

    try:
        auth_session_id = int(claims["sid"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError("AUTH_SESSION_MISSING", "访问令牌缺少会话标识", status_code=401) from exc

    await validate_auth_session(session, auth_session_id=auth_session_id)

    repository = IdentityRepository(session)
    user = await repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("AUTH_USER_NOT_FOUND", "登录用户不存在", status_code=401)
    if user.status != "active":
        raise AppError("AUTH_USER_DISABLED", "用户状态不可用", status_code=403)

    return CurrentUser(user=user, claims=claims)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
    session: AsyncSession = Depends(get_session),
) -> CurrentUser:
    """
    FastAPI 当前用户依赖。

    使用 HTTPBearer 声明安全方案后，Swagger 会给依赖该函数的接口显示锁标识；
    实际 token 和会话校验仍复用 resolve_current_user_from_authorization。
    """

    if credentials is None:
        authorization = None
    else:
        authorization = f"{credentials.scheme} {credentials.credentials}"

    return await resolve_current_user_from_authorization(
        authorization=authorization,
        session=session,
    )


def require_permission(
    permission_code: str,
    *,
    scope_type: str | None = None,
    scope_id: int | None = None,
):
    """
    构造权限点依赖。

    Args:
        permission_code: 需要检查的稳定权限点 code。
        scope_type: 可选作用域类型，例如 global、department、project。
        scope_id: 可选作用域 ID。

    Returns:
        FastAPI 依赖函数，验证通过时返回 CurrentUser。
    """

    async def dependency(
        request: Request,
        current: CurrentUser = Depends(get_current_user),
        session: AsyncSession = Depends(get_session),
    ) -> CurrentUser:
        """执行权限检查并把拒绝结果转换成统一 403。"""

        decision = await check_user_permission(
            session,
            user_id=current.user.id,
            permission_code=permission_code,
            scope_type=scope_type,
            scope_id=scope_id,
        )
        if not decision.allowed:
            try:
                await record_audit_log(
                    session,
                    AuditLogEntry(
                        actor_id=current.user.id,
                        action="permission.denied",
                        target_type="permission",
                        target_id=permission_code,
                        result="denied",
                        risk_level="medium",
                        ip_address=get_client_ip(request),
                        user_agent=request.headers.get("user-agent"),
                        request_id=get_request_id(request),
                        reason=decision.reason,
                        extra={
                            "method": request.method,
                            "path": request.url.path,
                            "permission_code": permission_code,
                            "scope_type": scope_type,
                            "scope_id": scope_id,
                        },
                    ),
                )
                await session.commit()
            except Exception:
                # 权限拒绝不能因为审计写入失败而变成放行；记录运行日志后继续返回 403。
                await session.rollback()
                logger.exception(
                    "权限拒绝审计写入失败 | user_id={} permission_code={}",
                    current.user.id,
                    permission_code,
                )
            raise AppError(
                "PERMISSION_DENIED",
                "当前用户无权执行该操作",
                status_code=403,
                details={
                    "permission_code": permission_code,
                    "reason": decision.reason,
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                },
            )
        return current

    return dependency
