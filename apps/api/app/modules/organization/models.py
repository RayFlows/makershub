# app/modules/organization/models.py
"""
组织与成员数据库模型

本文件负责组织域的基础数据结构：部门、成员资料、部门成员关系和职务关系。
登录凭证仍由 identity 域负责，这里只描述“这个人在协会里的资料和归属”。

旧后端曾把 openid、个人资料、部门、积分都放在 users 表。重构后必须拆开：
users 只表示内部用户主体，member_profiles 承接真实姓名、手机号、学号等业务资料，
departments/department_memberships 承接协会组织关系，积分后续进入独立账本域。
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin


class Department(Base, IdMixin, TimestampMixin):
    """
    协会部门定义表。

    部门是组织数据，不是代码模块。它可以参与权限作用域判断，
    但不能直接替代权限点或业务域边界。
    """

    __tablename__ = "departments"

    # --- 部门基础信息 ---
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)

    # --- 组织关系 ---
    memberships: Mapped[list[DepartmentMembership]] = relationship(back_populates="department")
    user_positions: Mapped[list[UserPosition]] = relationship(back_populates="department")


class MemberProfile(Base, IdMixin, TimestampMixin):
    """
    成员资料表。

    这里承接旧小程序用户资料中的 real_name、phone_num、student_id、qq、college、grade 等字段。
    新表使用 phone 表达手机号；后续小程序适配旧字段时，可以在接口适配层映射为 phone_num。
    """

    __tablename__ = "member_profiles"

    # --- 账号归属 ---
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )

    # --- 基础资料 ---
    real_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    student_id: Mapped[str | None] = mapped_column(String(32), nullable=True, unique=True)
    phone: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    college: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    major: Mapped[str | None] = mapped_column(String(100), nullable=True)
    grade: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    qq: Mapped[str | None] = mapped_column(String(20), nullable=True)
    bio: Mapped[str | None] = mapped_column(Text, nullable=True)


class DepartmentMembership(Base, IdMixin, TimestampMixin):
    """
    部门成员关系表。

    一个用户可以有历史部门记录，但同一时间的有效部门关系由 status/left_at 表达。
    后续后台成员管理需要在服务层限制同一用户的有效部门关系数量。
    """

    __tablename__ = "department_memberships"

    # --- 关系主体 ---
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=False,
    )

    # --- 生命周期 ---
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    department: Mapped[Department] = relationship(back_populates="memberships")

    __table_args__ = (
        Index("ix_department_memberships_user_id_status", "user_id", "status"),
        Index("ix_department_memberships_department_id_status", "department_id", "status"),
    )


class Position(Base, IdMixin, TimestampMixin):
    """
    职务定义表。

    code 是稳定业务代码，不能依赖 sort_order 做接口鉴权。
    998/999 这类底层管理身份通过 is_system 标记，避免和普通协会职务混淆。
    """

    __tablename__ = "positions"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user_positions: Mapped[list[UserPosition]] = relationship(back_populates="position")


class UserPosition(Base, IdMixin, TimestampMixin):
    """
    用户职务关系表。

    一个用户可以拥有多个职务或系统身份；revoked_at 为空表示当前有效。
    scope_type/scope_id 为后续“本部门、本项目、全局”等作用域授权预留。
    """

    __tablename__ = "user_positions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    position_id: Mapped[int] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
    )
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    scope_id: Mapped[int | None] = mapped_column(nullable=True)
    granted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    position: Mapped[Position] = relationship(back_populates="user_positions")
    department: Mapped[Department | None] = relationship(back_populates="user_positions")

    __table_args__ = (
        Index("ix_user_positions_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_user_positions_position_id_revoked_at", "position_id", "revoked_at"),
    )
