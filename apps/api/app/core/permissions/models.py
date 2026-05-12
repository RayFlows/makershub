# app/core/permissions/models.py
"""
权限数据库模型

权限系统回答“用户能不能做某件事”。它和 identity 的登录身份分开，
也和 organization 的部门/职务资料分开。业务接口必须检查权限点和作用域，
不能继续使用 `identity_code >= 1` 这类数字比较。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin
from app.shared.time import utc_now


class Permission(Base, IdMixin, TimestampMixin):
    """
    权限点表。

    code 是接口、后台菜单和审计日志共同依赖的稳定契约，不能随意改名。
    """

    __tablename__ = "permissions"

    # --- 权限点定义 ---
    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    module: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="low", index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    role_permissions: Mapped[list[RolePermission]] = relationship(back_populates="permission")


class Role(Base, IdMixin, TimestampMixin):
    """
    角色表。

    角色是一组权限点的集合；真实授权还需要 user_role_grants 上的作用域。
    """

    __tablename__ = "roles"

    # --- 角色定义 ---
    code: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    role_permissions: Mapped[list[RolePermission]] = relationship(back_populates="role")
    user_role_grants: Mapped[list[UserRoleGrant]] = relationship(back_populates="role")


class RolePermission(Base, TimestampMixin):
    """
    角色权限关系表。

    这是一张纯链接表，连接 roles.id 和 permissions.id：
    - roles 记录“角色是什么”，例如 organization_manager；
    - permissions 记录“权限点是什么”，例如 organization.member.manage；
    - role_permissions 记录“某个角色包含哪些权限点”。

    表里只存数字外键是为了避免重复保存角色名和权限名；需要人类可读信息时，
    后台或排查 SQL 应该 join roles 和 permissions。复合主键避免同一角色重复
    绑定同一权限点。
    """

    __tablename__ = "role_permissions"

    role_id: Mapped[int] = mapped_column(
        ForeignKey("roles.id", ondelete="RESTRICT"),
        primary_key=True,
    )
    permission_id: Mapped[int] = mapped_column(
        ForeignKey("permissions.id", ondelete="RESTRICT"),
        primary_key=True,
    )

    role: Mapped[Role] = relationship(back_populates="role_permissions")
    permission: Mapped[Permission] = relationship(back_populates="role_permissions")


class UserRoleGrant(Base, IdMixin, TimestampMixin):
    """
    用户角色授权表。

    scope_type/scope_id 用来表达全局、部门、项目、资源等作用域。
    revoked_at 为空表示当前有效，历史授权记录保留用于审计追溯。
    """

    __tablename__ = "user_role_grants"

    # --- 授权主体 ---
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    role_id: Mapped[int] = mapped_column(ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False)

    # --- 作用域 ---
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    scope_id: Mapped[int | None] = mapped_column(nullable=True)

    # --- 授权生命周期 ---
    granted_by: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: utc_now(),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    role: Mapped[Role] = relationship(back_populates="user_role_grants")

    __table_args__ = (
        Index("ix_user_role_grants_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_user_role_grants_role_id_revoked_at", "role_id", "revoked_at"),
        Index("ix_user_role_grants_scope", "scope_type", "scope_id"),
    )
