# app/core/permissions/service.py
"""
权限服务层

本文件负责把权限点注册表、数据库角色授权和系统职务映射成统一判断结果。
业务接口只应该依赖 `check_user_permission` 或 HTTP 层的 `require_permission`，
不要再直接比较职务数字或部门编号。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.permissions.models import UserRoleGrant
from app.core.permissions.registry import permission_registry
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.types import PermissionDecision
from app.modules.identity.repositories import IdentityRepository
from app.modules.organization.models import Department

# --- 系统权限常量 ---
SYSTEM_ADMIN_PERMISSION_CODES = frozenset(
    {
        "system.admin.access",
        "system.audit.view",
        "system.permission.manage",
        "files.manage",
        "points.manual.adjust",
    },
)
"""
998 和 999 共同拥有的系统兜底权限。

这些权限服务系统管理、异常修复和受控兜底，不包含组织、积分、资源、借用等日常
业务审批权限。需要日常业务能力时，应通过角色授权显式授予。
"""


SUPER_ADMIN_ONLY_PERMISSION_CODES = frozenset(
    {
        "system.operator.manage",
        "system.super_admin.recover",
    },
)
"""
唯一 999 额外拥有的母账号权限。

999 出现的核心原因是系统需要一个母账号来初始化、指定或恢复 998。除这些母账号
动作外，998 与 999 的系统兜底能力保持一致。
"""


SYSTEM_OPERATOR_ROLE_CODES = frozenset({"system_super_admin", "system_operator"})
"""
不能通过普通权限写接口授予的系统底层角色。

998 与 999 的入口来自系统职务，不来自普通角色授权。999 唯一多出来的能力是指定或
恢复 998；把这两个角色挡在通用授权接口之外，可以避免后台业务管理员误把底层兜底
身份当成日常业务角色分配。
"""


SUPPORTED_USER_ROLE_SCOPE_TYPES = frozenset({"global", "department"})
"""第一阶段用户角色授权支持的作用域类型。"""


# --- 服务层数据结构 ---
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


# --- 预置角色定义 ---
DEFAULT_ROLE_DEFINITIONS: tuple[RoleDefinition, ...] = (
    RoleDefinition(
        code="system_super_admin",
        name="超级管理员",
        description="系统唯一 999 母账号，用于初始化、指定或恢复 998。",
        permission_codes=tuple(sorted(SYSTEM_ADMIN_PERMISSION_CODES | SUPER_ADMIN_ONLY_PERMISSION_CODES)),
    ),
    RoleDefinition(
        code="system_operator",
        name="系统运维管理员",
        description="998 管理由唯一 999 指定，拥有系统兜底权限。",
        permission_codes=tuple(sorted(SYSTEM_ADMIN_PERMISSION_CODES)),
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
    RoleDefinition(
        code="points_manager",
        name="积分账本查看员",
        description="查看成员积分账户和积分流水，不包含人工调整积分能力。",
        permission_codes=("system.admin.access", "points.ledger.view"),
    ),
    RoleDefinition(
        code="points_rule_applicant",
        name="临时积分规则申请人",
        description="提交特殊非模板任务的临时积分规则申请。",
        permission_codes=(
            "system.admin.access",
            "points.rule.view",
            "points.temporary_rule.apply",
        ),
    ),
    RoleDefinition(
        code="points_rule_reviewer",
        name="临时积分规则审批员",
        description="审批、驳回和撤回临时积分规则，不包含系统兜底人工改分。",
        permission_codes=(
            "system.admin.access",
            "points.ledger.view",
            "points.rule.view",
            "points.temporary_rule.review",
        ),
    ),
    RoleDefinition(
        code="points_rule_manager",
        name="积分规则管理员",
        description="维护固定积分规则，并处理临时积分规则申请和审批。",
        permission_codes=(
            "system.admin.access",
            "points.ledger.view",
            "points.rule.view",
            "points.rule.manage",
            "points.temporary_rule.apply",
            "points.temporary_rule.review",
        ),
    ),
    RoleDefinition(
        code="workbench_task_publisher",
        name="工作台任务发布人",
        description="发布指定任务和悬赏任务，审核自己发布任务的完成结果。",
        permission_codes=("system.admin.access", "points.rule.view", "workbench.task.publish"),
    ),
    RoleDefinition(
        code="resource_manager",
        name="资源与借用管理员",
        description="基管部常态职责打包角色：维护物资台账，审核物资借用申请，并确认归还。",
        permission_codes=(
            "system.admin.access",
            "resources.material.manage",
            "borrowing.application.review",
        ),
    ),
)


# --- 权限注册同步 ---
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

    for role_definition in DEFAULT_ROLE_DEFINITIONS:
        role = await repository.upsert_role(
            code=role_definition.code,
            name=role_definition.name,
            description=role_definition.description,
            is_system=role_definition.is_system,
        )
        await repository.replace_role_permissions(role, role_definition.permission_codes or ())

    return PermissionSyncResult(
        permission_count=len(points),
        role_count=len(DEFAULT_ROLE_DEFINITIONS),
    )


# --- 用户角色授权 ---
async def list_user_role_grants(
    session: AsyncSession,
    *,
    user_id: int,
    include_revoked: bool = True,
) -> list[UserRoleGrant]:
    """
    列出某个用户的角色授权记录。

    该接口服务后台权限页，默认带出已撤销记录，方便运维回看“谁在什么时候给过什么权限”。
    """

    await _ensure_user_exists(session, user_id=user_id)
    repository = PermissionRepository(session)
    return await repository.list_user_role_grants(user_id=user_id, include_revoked=include_revoked)


async def grant_user_role(
    session: AsyncSession,
    *,
    user_id: int,
    role_code: str,
    actor_id: int,
    scope_type: str = "global",
    scope_id: int | None = None,
) -> UserRoleGrant:
    """
    给用户授予业务角色。

    注意:
        998/999 不通过本函数产生。它们是底层系统职务，由 999 专门指定或运维初始化；
        这里仅处理组织管理、审计查看等可审计的业务角色授权。
    """

    await _ensure_user_exists(session, user_id=user_id)
    normalized_scope_type, normalized_scope_id = await _normalize_user_role_grant_scope(
        session,
        scope_type=scope_type,
        scope_id=scope_id,
    )

    repository = PermissionRepository(session)
    role = await repository.get_role_by_code(role_code.strip())
    if role is None:
        raise AppError("ROLE_NOT_FOUND", "角色不存在", status_code=404)
    if role.status != "active":
        raise AppError("ROLE_INACTIVE", "角色未启用，不能授权", status_code=409)
    if role.code in SYSTEM_OPERATOR_ROLE_CODES:
        raise AppError(
            "SYSTEM_ROLE_GRANT_FORBIDDEN",
            "998/999 系统底层角色不能通过普通权限接口授予",
            status_code=403,
        )

    user_role_grant = await repository.grant_role_to_user(
        user_id=user_id,
        role=role,
        granted_by=actor_id,
        scope_type=normalized_scope_type,
        scope_id=normalized_scope_id,
    )
    await session.flush()
    return user_role_grant


async def revoke_user_role_grant(
    session: AsyncSession,
    *,
    user_role_grant_id: int,
) -> UserRoleGrant:
    """
    撤销用户角色授权。

    撤销只写入 revoked_at，不删除历史记录。这样审计日志、后台权限页和后续异常追溯
    都能看到完整授权链路。
    """

    repository = PermissionRepository(session)
    user_role_grant = await repository.get_user_role_grant_by_id(user_role_grant_id)
    if user_role_grant is None:
        raise AppError("USER_ROLE_GRANT_NOT_FOUND", "用户角色授权记录不存在", status_code=404)
    if user_role_grant.role is not None and user_role_grant.role.code in SYSTEM_OPERATOR_ROLE_CODES:
        raise AppError(
            "SYSTEM_ROLE_REVOKE_FORBIDDEN",
            "998/999 系统底层角色不能通过普通权限接口撤销",
            status_code=403,
        )
    if user_role_grant.revoked_at is not None:
        return user_role_grant

    user_role_grant = await repository.revoke_user_role_grant(user_role_grant)
    await session.flush()
    return user_role_grant


# --- 权限判断 ---
async def get_user_permission_summary(
    session: AsyncSession,
    *,
    user_id: int,
    scope_type: str | None = None,
    scope_id: int | None = None,
) -> UserPermissionSummary:
    """
    获取用户权限摘要。

    `998` 与 `999` 共同拥有系统兜底权限；`999` 额外拥有母账号动作权限。
    普通业务权限不因 998/999 自动获得，仍应通过业务角色或作用域授权显式授予。
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
        permission_codes.update(SYSTEM_ADMIN_PERMISSION_CODES | SUPER_ADMIN_ONLY_PERMISSION_CODES)
    elif is_system_operator:
        permission_codes.update(SYSTEM_ADMIN_PERMISSION_CODES)

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
    is_super_admin = await repository.user_has_system_position(user_id=user_id, position_code="999")
    if is_super_admin and permission_code in SYSTEM_ADMIN_PERMISSION_CODES | SUPER_ADMIN_ONLY_PERMISSION_CODES:
        return PermissionDecision(
            allowed=True,
            permission_code=permission_code,
            reason="999 母账号权限放行",
            scope_type=scope_type,
            scope_id=scope_id,
        )

    is_system_operator = await repository.user_has_system_position(
        user_id=user_id,
        position_code="998",
    )
    if is_system_operator and permission_code in SYSTEM_ADMIN_PERMISSION_CODES:
        return PermissionDecision(
            allowed=True,
            permission_code=permission_code,
            reason="998 系统兜底权限放行",
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


# --- 内部校验工具 ---
async def _ensure_user_exists(session: AsyncSession, *, user_id: int) -> None:
    """确认授权目标用户存在。"""

    identity_repository = IdentityRepository(session)
    user = await identity_repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)


async def _normalize_user_role_grant_scope(
    session: AsyncSession,
    *,
    scope_type: str,
    scope_id: int | None,
) -> tuple[str, int | None]:
    """
    规范化角色作用域。

    第一阶段只落地全局和部门作用域。项目、资源、场地等作用域必须等对应业务域模型
    完整后再开放，避免写入无法校验的权限边界。
    """

    normalized_scope_type = scope_type.strip().lower() if scope_type else "global"
    if normalized_scope_type not in SUPPORTED_USER_ROLE_SCOPE_TYPES:
        raise AppError("PERMISSION_SCOPE_UNSUPPORTED", "暂不支持该权限作用域", status_code=422)

    if normalized_scope_type == "global":
        if scope_id is not None:
            raise AppError("PERMISSION_SCOPE_INVALID", "全局授权不能携带 scope_id", status_code=422)
        return normalized_scope_type, None

    if scope_id is None:
        raise AppError("PERMISSION_SCOPE_INVALID", "部门作用域授权必须指定部门 ID", status_code=422)

    department = await session.scalar(
        select(Department).where(Department.id == scope_id, Department.status == "active"),
    )
    if department is None:
        raise AppError("DEPARTMENT_NOT_FOUND", "部门不存在或未启用", status_code=404)
    return normalized_scope_type, scope_id
