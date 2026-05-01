# app/core/permissions/service.py
"""
权限服务层

本文件负责把权限点注册表、数据库角色授权和系统职务桥接成统一判断结果。
业务接口只应该依赖 `check_user_permission` 或 HTTP 层的 `require_permission`，
不要再直接比较职务数字或部门编号。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.repository import PermissionRepository
from app.core.permissions.registry import permission_registry
from app.core.permissions.types import PermissionDecision


SYSTEM_OPERATOR_PERMISSION_CODES = frozenset(
    {
        "system.admin.access",
        "system.audit.view",
        "system.permission.manage",
        "files.manage",
    },
)
"""
998 管理员的底层运维权限。

需求文档明确 998/999 不作为日常业务审批角色，因此这里不给 998 自动授予
组织管理、积分审批、资源审核等业务权限。业务授权应该通过角色和作用域单独授予。
"""


@dataclass(frozen=True)
class RoleDefinition:
    """系统预置角色定义。"""

    code: str
    name: str
    description: str
    permission_codes: tuple[str, ...] | None
    is_system: bool = True


@dataclass(frozen=True)
class PermissionSyncResult:
    """权限种子同步结果。"""

    permission_count: int
    role_count: int


@dataclass(frozen=True)
class UserPermissionSummary:
    """当前用户权限摘要。"""

    user_id: int
    permissions: tuple[str, ...]
    is_super_admin: bool
    is_system_operator: bool


DEFAULT_ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        code="system_super_admin",
        name="超级管理员",
        description="系统唯一 999 兜底身份对应的完整权限集合。",
        permission_codes=None,
    ),
    RoleDefinition(
        code="system_operator",
        name="系统运维管理员",
        description="998 系统身份对应的运维权限，不包含日常业务审批权限。",
        permission_codes=tuple(sorted(SYSTEM_OPERATOR_PERMISSION_CODES)),
    ),
    RoleDefinition(
        code="organization_manager",
        name="组织管理人员",
        description="维护成员资料、部门归属和职务关系的业务管理角色。",
        permission_codes=(
            "system.admin.access",
            "organization.member.manage",
            "organization.department.manage",
            "organization.position.manage",
        ),
    ),
    RoleDefinition(
        code="auditor",
        name="审计查看员",
        description="查看系统审计日志和高风险操作记录。",
        permission_codes=("system.admin.access", "system.audit.view"),
    ),
)


async def sync_registered_permissions(session: AsyncSession) -> PermissionSyncResult:
    """
    把内存权限注册表同步到数据库。

    该函数用于迁移种子之外的本地修复、测试准备和后续运维命令。它是幂等的，
    但不自动提交事务，调用方需要显式 commit。
    """

    repository = PermissionRepository(session)
    points = permission_registry.list()
    for point in points:
        await repository.upsert_permission_point(point)
    await session.flush()

    all_codes = tuple(point.code for point in points)
    for role_definition in DEFAULT_ROLE_DEFINITIONS:
        role = await repository.upsert_role(
            code=role_definition.code,
            name=role_definition.name,
            description=role_definition.description,
            is_system=role_definition.is_system,
        )
        permission_codes = role_definition.permission_codes or all_codes
        await repository.replace_role_permissions(role, permission_codes)

    return PermissionSyncResult(
        permission_count=len(points),
        role_count=len(DEFAULT_ROLE_DEFINITIONS),
    )


async def get_user_permission_summary(
    session: AsyncSession,
    *,
    user_id: int,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> UserPermissionSummary:
    """
    获取用户权限摘要。

    `999` 返回全部已注册权限点；`998` 返回底层运维权限；普通用户只返回数据库
    角色授权得到的权限点。这样可以让后台菜单和接口鉴权使用同一套结果。
    """

    repository = PermissionRepository(session)
    is_super_admin = await repository.user_has_system_position(
        user_id=user_id,
        position_code="999",
    )
    is_system_operator = await repository.user_has_system_position(
        user_id=user_id,
        position_code="998",
    )

    permission_codes: set[str] = set()
    if is_super_admin:
        permission_codes.update(point.code for point in permission_registry.list())
    if is_system_operator:
        permission_codes.update(SYSTEM_OPERATOR_PERMISSION_CODES)

    permission_codes.update(
        await repository.list_user_permission_codes(
            user_id=user_id,
            scope_type=scope_type,
            scope_id=scope_id,
        ),
    )

    registered_codes = {point.code for point in permission_registry.list()}
    known_codes = sorted(code for code in permission_codes if code in registered_codes)
    return UserPermissionSummary(
        user_id=user_id,
        permissions=tuple(known_codes),
        is_super_admin=is_super_admin,
        is_system_operator=is_system_operator,
    )


async def check_user_permission(
    session: AsyncSession,
    *,
    user_id: int,
    permission_code: str,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> PermissionDecision:
    """
    判断用户是否拥有目标权限点。

    Returns:
        PermissionDecision，调用方根据 allowed 决定继续执行或返回 403。
    """

    if permission_registry.get(permission_code) is None:
        return PermissionDecision(
            allowed=False,
            permission_code=permission_code,
            reason="权限点未注册",
            scope_type=scope_type,
            scope_id=scope_id,
        )

    repository = PermissionRepository(session)
    if await repository.user_has_system_position(user_id=user_id, position_code="999"):
        return PermissionDecision(
            allowed=True,
            permission_code=permission_code,
            reason="999 超级管理员兜底放行",
            scope_type=scope_type,
            scope_id=scope_id,
        )

    if (
        permission_code in SYSTEM_OPERATOR_PERMISSION_CODES
        and await repository.user_has_system_position(user_id=user_id, position_code="998")
    ):
        return PermissionDecision(
            allowed=True,
            permission_code=permission_code,
            reason="998 系统运维权限放行",
            scope_type=scope_type,
            scope_id=scope_id,
        )

    allowed = await repository.user_has_permission(
        user_id=user_id,
        permission_code=permission_code,
        scope_type=scope_type,
        scope_id=scope_id,
    )
    return PermissionDecision(
        allowed=allowed,
        permission_code=permission_code,
        reason="角色授权命中" if allowed else "用户未被授予该权限点或作用域不匹配",
        scope_type=scope_type,
        scope_id=scope_id,
    )
