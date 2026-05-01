# app/interfaces/http/v1/permissions/router.py
"""
权限 V1 路由

本路由主要服务后台管理端和本地调试：查看当前用户拥有的权限、查看系统权限点
和角色。修改授权关系后续需要审计接入后再开放写接口。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import get_user_permission_summary
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.permissions.schemas import (
    CurrentUserPermissions,
    PermissionItem,
    RoleItem,
)
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter(prefix="/permissions")


@router.get("/me")
async def get_my_permissions(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前用户权限摘要，用于后台菜单过滤和前端启动态判断。"""

    summary = await get_user_permission_summary(session, user_id=current.user.id)
    data = CurrentUserPermissions(
        user_id=summary.user_id,
        permissions=list(summary.permissions),
        is_super_admin=summary.is_super_admin,
        is_system_operator=summary.is_system_operator,
    )
    return success_response(data.model_dump(), request_id=get_request_id(request))


@router.get("")
async def list_permissions(
    request: Request,
    _: CurrentUser = Depends(require_permission("system.admin.access")),
    session: AsyncSession = Depends(get_session),
):
    """
    查看系统权限点。

    只要求后台访问权限，不要求权限维护权限，方便业务管理员确认自己可见能力。
    """

    repository = PermissionRepository(session)
    permissions = await repository.list_permissions(active_only=False)
    data = [
        PermissionItem(
            code=item.code,
            name=item.name,
            module=item.module,
            description=item.description,
            risk_level=item.risk_level,
            status=item.status,
        ).model_dump()
        for item in permissions
    ]
    return success_response({"permissions": data}, request_id=get_request_id(request))


@router.get("/roles")
async def list_roles(
    request: Request,
    _: CurrentUser = Depends(require_permission("system.permission.manage")),
    session: AsyncSession = Depends(get_session),
):
    """查看角色和角色包含的权限点。"""

    repository = PermissionRepository(session)
    roles = await repository.list_roles(active_only=False)
    data: list[dict] = []
    for role in roles:
        permission_codes = set()
        for relation in role.role_permissions:
            if relation.permission is not None:
                permission_codes.add(relation.permission.code)
        data.append(
            RoleItem(
                code=role.code,
                name=role.name,
                description=role.description,
                is_system=role.is_system,
                status=role.status,
                permissions=sorted(permission_codes),
            ).model_dump(),
        )
    return success_response({"roles": data}, request_id=get_request_id(request))

