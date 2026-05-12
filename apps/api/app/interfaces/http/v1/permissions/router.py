# app/interfaces/http/v1/permissions/router.py
"""
权限 V1 路由

本路由服务后台管理端和本地调试：查看当前用户拥有的权限、查看系统权限点和角色，
并提供带审计的业务角色授权/撤销接口。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.permissions.models import UserRoleGrant
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import (
    get_user_permission_summary,
    grant_user_role,
    revoke_user_role_grant,
)
from app.core.permissions.service import (
    list_user_role_grants as list_user_role_grants_service,
)
from app.core.security.middleware import get_client_ip
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.permissions.schemas import (
    CurrentUserPermissions,
    GrantUserRoleRequest,
    PermissionItem,
    RevokeUserRoleGrantRequest,
    RoleItem,
    UserRoleGrantItem,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter(prefix="/permissions")


# --- 响应转换 ---
def build_user_role_grant_item(user_role_grant: UserRoleGrant) -> UserRoleGrantItem:
    """把用户角色授权 ORM 对象转换成接口响应。"""

    role = user_role_grant.role
    return UserRoleGrantItem(
        id=user_role_grant.id,
        user_id=user_role_grant.user_id,
        role_code=role.code if role is not None else "",
        role_name=role.name if role is not None else "",
        scope_type=user_role_grant.scope_type,
        scope_id=user_role_grant.scope_id,
        granted_by=user_role_grant.granted_by,
        granted_at=user_role_grant.granted_at,
        revoked_at=user_role_grant.revoked_at,
    )


def build_user_role_grant_snapshot(user_role_grant: UserRoleGrant) -> dict:
    """构造审计日志使用的授权快照。"""

    return build_user_role_grant_item(user_role_grant).model_dump(mode="json")


# --- 权限查询 ---
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


# --- 用户角色授权写接口 ---
@router.get("/users/{user_id}/roles")
async def list_user_role_grant_records(
    user_id: int,
    request: Request,
    _: CurrentUser = Depends(require_permission("system.permission.manage")),
    session: AsyncSession = Depends(get_session),
):
    """
    查看某个用户的角色授权记录。

    默认返回包含已撤销记录的完整链路，方便后台权限页和运维追溯。
    """

    grants = await list_user_role_grants_service(session, user_id=user_id, include_revoked=True)
    data = [build_user_role_grant_item(item).model_dump(mode="json") for item in grants]
    return success_response({"roles": data}, request_id=get_request_id(request))


@router.post("/users/{user_id}/roles")
async def grant_role_to_user_endpoint(
    user_id: int,
    payload: GrantUserRoleRequest,
    request: Request,
    current: CurrentUser = Depends(require_permission("system.permission.manage")),
    session: AsyncSession = Depends(get_session),
):
    """
    给用户授予业务角色。

    该接口不负责指定 998/999。底层系统身份必须走专门的 999 指定或运维初始化流程，
    避免普通权限维护入口误触系统兜底身份。
    """

    user_role_grant = await grant_user_role(
        session,
        user_id=user_id,
        role_code=payload.role_code,
        actor_id=current.user.id,
        scope_type=payload.scope_type,
        scope_id=payload.scope_id,
    )
    after_snapshot = build_user_role_grant_snapshot(user_role_grant)
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current.user.id,
            action="permission.user_role_grant.create",
            target_type="user_role_grant",
            target_id=str(user_role_grant.id),
            after_snapshot=after_snapshot,
            extra={"target_user_id": user_id, "role_code": payload.role_code},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    return success_response(after_snapshot, request_id=get_request_id(request))


@router.post("/role-grants/{user_role_grant_id}/revoke")
async def revoke_role_from_user_endpoint(
    user_role_grant_id: int,
    payload: RevokeUserRoleGrantRequest,
    request: Request,
    current: CurrentUser = Depends(require_permission("system.permission.manage")),
    session: AsyncSession = Depends(get_session),
):
    """撤销一条用户角色授权，并保留审计记录。"""

    repository = PermissionRepository(session)
    existing = await repository.get_user_role_grant_by_id(user_role_grant_id)
    before_snapshot = build_user_role_grant_snapshot(existing) if existing is not None else None
    user_role_grant = await revoke_user_role_grant(session, user_role_grant_id=user_role_grant_id)
    after_snapshot = build_user_role_grant_snapshot(user_role_grant)
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current.user.id,
            action="permission.user_role_grant.revoke",
            target_type="user_role_grant",
            target_id=str(user_role_grant.id),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            extra={"target_user_id": user_role_grant.user_id, "role_code": after_snapshot["role_code"]},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    return success_response(after_snapshot, request_id=get_request_id(request))
