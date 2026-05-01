# app/core/permissions/repository.py
"""
权限数据库访问层

本文件只封装权限相关表的 SQLAlchemy 查询，不直接决定业务接口是否放行。
真正的授权规则放在 service.py，HTTP 层再通过依赖把拒绝结果转换成 403。
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Iterable

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.permissions.models import Permission, Role, RolePermission, UserRole
from app.core.permissions.registry import PermissionPoint
from app.modules.organization.models import Position, UserPosition


class PermissionRepository:
    """
    权限表仓储。

    仓储层不提交事务，调用方需要在服务或接口层决定 commit/rollback 边界。
    """

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- 权限点 ---
    async def get_permission_by_code(self, code: str) -> Permission | None:
        """按稳定 code 查询权限点。"""

        return await self.session.scalar(select(Permission).where(Permission.code == code))

    async def list_permissions(self, *, active_only: bool = True) -> list[Permission]:
        """列出权限点。"""

        stmt = select(Permission).order_by(Permission.module, Permission.code)
        if active_only:
            stmt = stmt.where(Permission.status == "active")
        result = await self.session.scalars(stmt)
        return list(result)

    async def upsert_permission_point(self, point: PermissionPoint) -> Permission:
        """
        根据注册表同步权限点。

        权限 code 进入数据库后保持稳定；name、description、module 和 risk_level
        可以随文档完善做幂等更新。
        """

        permission = await self.get_permission_by_code(point.code)
        if permission is None:
            permission = Permission(
                code=point.code,
                name=point.name,
                description=point.description,
                module=point.module,
                risk_level=point.risk_level.value,
                status="active",
            )
            self.session.add(permission)
            return permission

        permission.name = point.name
        permission.description = point.description
        permission.module = point.module
        permission.risk_level = point.risk_level.value
        permission.status = "active"
        return permission

    # --- 角色 ---
    async def get_role_by_code(self, code: str) -> Role | None:
        """按稳定 code 查询角色。"""

        return await self.session.scalar(select(Role).where(Role.code == code))

    async def list_roles(self, *, active_only: bool = True) -> list[Role]:
        """列出角色。"""

        stmt = select(Role).options(
            selectinload(Role.role_permissions).selectinload(RolePermission.permission),
        ).order_by(Role.code)
        if active_only:
            stmt = stmt.where(Role.status == "active")
        result = await self.session.scalars(stmt)
        return list(result)

    async def upsert_role(
        self,
        *,
        code: str,
        name: str,
        description: str,
        is_system: bool,
    ) -> Role:
        """创建或更新系统预置角色。"""

        role = await self.get_role_by_code(code)
        if role is None:
            role = Role(
                code=code,
                name=name,
                description=description,
                is_system=is_system,
                status="active",
            )
            self.session.add(role)
            return role

        role.name = name
        role.description = description
        role.is_system = is_system
        role.status = "active"
        return role

    async def replace_role_permissions(self, role: Role, permission_codes: Iterable[str]) -> None:
        """
        用权限 code 列表重建角色权限关系。

        预置角色的权限来自代码注册表，重建比局部增删更容易保持幂等。
        """

        await self.session.flush()
        permissions = await self.session.scalars(
            select(Permission).where(Permission.code.in_(set(permission_codes))),
        )
        permission_by_code = {item.code: item for item in permissions}

        current = await self.session.scalars(
            select(RolePermission).where(RolePermission.role_id == role.id),
        )
        for relation in current:
            await self.session.delete(relation)
        await self.session.flush()

        for code in sorted(set(permission_codes)):
            permission = permission_by_code.get(code)
            if permission is not None:
                self.session.add(RolePermission(role_id=role.id, permission_id=permission.id))

    # --- 用户授权 ---
    async def list_user_permission_codes(
        self,
        *,
        user_id: int,
        scope_type: str | None = None,
        scope_id: int | None = None,
    ) -> set[str]:
        """查询用户通过角色授权得到的权限点 code。"""

        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.revoked_at.is_(None),
                Role.status == "active",
                Permission.status == "active",
            )
        )
        if scope_type is not None:
            stmt = stmt.where(self._build_scope_clause(scope_type=scope_type, scope_id=scope_id))

        result = await self.session.scalars(stmt)
        return set(result)

    async def user_has_permission(
        self,
        *,
        user_id: int,
        permission_code: str,
        scope_type: str | None = None,
        scope_id: int | None = None,
    ) -> bool:
        """检查用户是否通过角色授权拥有某个权限点。"""

        stmt = (
            select(Permission.id)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(
                UserRole.user_id == user_id,
                UserRole.revoked_at.is_(None),
                Role.status == "active",
                Permission.status == "active",
                Permission.code == permission_code,
            )
            .limit(1)
        )
        if scope_type is not None:
            stmt = stmt.where(self._build_scope_clause(scope_type=scope_type, scope_id=scope_id))

        return await self.session.scalar(stmt) is not None

    async def grant_role_to_user(
        self,
        *,
        user_id: int,
        role: Role,
        granted_by: int | None = None,
        scope_type: str = "global",
        scope_id: int | None = None,
    ) -> UserRole:
        """给用户授予角色。"""

        existing = await self.session.scalar(
            select(UserRole).where(
                UserRole.user_id == user_id,
                UserRole.role_id == role.id,
                UserRole.scope_type == scope_type,
                UserRole.scope_id == scope_id,
                UserRole.revoked_at.is_(None),
            ),
        )
        if existing is not None:
            return existing

        user_role = UserRole(
            user_id=user_id,
            role_id=role.id,
            scope_type=scope_type,
            scope_id=scope_id,
            granted_by=granted_by,
            granted_at=datetime.now(UTC),
        )
        self.session.add(user_role)
        return user_role

    async def revoke_user_role(self, user_role: UserRole) -> UserRole:
        """撤销一条用户角色授权，保留历史记录。"""

        user_role.revoked_at = datetime.now(UTC)
        return user_role

    # --- 系统职务映射 ---
    async def user_has_system_position(self, *, user_id: int, position_code: str) -> bool:
        """
        检查用户是否拥有有效系统职务。

        这里只用于兼容第一阶段的 998/999 系统身份。普通业务权限仍必须走权限点。
        """

        stmt = (
            select(UserPosition.id)
            .join(Position, Position.id == UserPosition.position_id)
            .where(
                UserPosition.user_id == user_id,
                UserPosition.revoked_at.is_(None),
                Position.code == position_code,
                Position.status == "active",
                Position.is_system.is_(True),
            )
            .limit(1)
        )
        return await self.session.scalar(stmt) is not None

    def _build_scope_clause(self, *, scope_type: str, scope_id: int | None):
        """构造作用域匹配条件。"""

        specific_scope = UserRole.scope_type == scope_type
        if scope_id is None:
            specific_scope = and_(specific_scope, UserRole.scope_id.is_(None))
        else:
            specific_scope = and_(specific_scope, UserRole.scope_id == scope_id)

        return or_(UserRole.scope_type == "global", specific_scope)
