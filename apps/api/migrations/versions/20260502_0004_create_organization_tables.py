# migrations/versions/20260502_0004_create_organization_tables.py
"""
创建组织与成员基础表

Revision ID: 20260502_0004
Revises: 20260429_0003
Create Date: 2026-05-02

需求背景:
旧系统把微信 openid、个人资料、部门和积分混在 users 表。重构后需要把身份登录
和协会组织资料拆开，先落地部门、成员资料和部门成员关系，为成员网页端个人资料、
后续花名册、后台成员管理和权限作用域做准备。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260502_0004"
down_revision = "20260429_0003"
branch_labels = None
depends_on = None


def timestamp_columns() -> list[sa.Column]:
    """生成迁移中重复使用的 created_at/updated_at 字段。"""

    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    """执行升级迁移。"""

    # --- 部门定义表 ---
    op.create_table(
        "departments",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_departments_code"),
    )
    op.create_index("ix_departments_status", "departments", ["status"])

    departments = sa.table(
        "departments",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("sort_order", sa.Integer()),
    )
    op.bulk_insert(
        departments,
        [
            {"code": "publicity", "name": "宣传部", "status": "active", "sort_order": 10},
            {"code": "infrastructure", "name": "基管部", "status": "active", "sort_order": 20},
            {"code": "project", "name": "项目部", "status": "active", "sort_order": 30},
            {"code": "operations", "name": "运维部", "status": "active", "sort_order": 40},
        ],
    )

    # --- 成员资料表 ---
    op.create_table(
        "member_profiles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("real_name", sa.String(length=100), nullable=True),
        sa.Column("student_id", sa.String(length=32), nullable=True),
        sa.Column("phone", sa.String(length=20), nullable=True),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("college", sa.String(length=100), nullable=True),
        sa.Column("major", sa.String(length=100), nullable=True),
        sa.Column("grade", sa.String(length=20), nullable=True),
        sa.Column("qq", sa.String(length=20), nullable=True),
        sa.Column("bio", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("student_id", name="uq_member_profiles_student_id"),
        sa.UniqueConstraint("user_id", name="uq_member_profiles_user_id"),
    )
    op.create_index("ix_member_profiles_college", "member_profiles", ["college"])
    op.create_index("ix_member_profiles_grade", "member_profiles", ["grade"])
    op.create_index("ix_member_profiles_phone", "member_profiles", ["phone"])

    # --- 部门成员关系表 ---
    op.create_table(
        "department_memberships",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "joined_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("left_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_department_memberships_department_id_status",
        "department_memberships",
        ["department_id", "status"],
    )
    op.create_index("ix_department_memberships_status", "department_memberships", ["status"])
    op.create_index(
        "ix_department_memberships_user_id_status",
        "department_memberships",
        ["user_id", "status"],
    )

    # user_positions.department_id 之前是预留字段，这里补齐部门外键约束。
    op.create_foreign_key(
        "fk_user_positions_department_id_departments",
        "user_positions",
        "departments",
        ["department_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    """执行回滚迁移。"""

    # 先删除依赖部门表的外键和关系表，再删除部门定义。
    op.drop_constraint(
        "fk_user_positions_department_id_departments",
        "user_positions",
        type_="foreignkey",
    )
    op.drop_index("ix_department_memberships_user_id_status", table_name="department_memberships")
    op.drop_index("ix_department_memberships_status", table_name="department_memberships")
    op.drop_index(
        "ix_department_memberships_department_id_status",
        table_name="department_memberships",
    )
    op.drop_table("department_memberships")
    op.drop_index("ix_member_profiles_phone", table_name="member_profiles")
    op.drop_index("ix_member_profiles_grade", table_name="member_profiles")
    op.drop_index("ix_member_profiles_college", table_name="member_profiles")
    op.drop_table("member_profiles")
    op.drop_index("ix_departments_status", table_name="departments")
    op.drop_table("departments")
