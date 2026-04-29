# migrations/versions/20260429_0001_create_identity_tables.py
"""
创建身份与职务基础表

Revision ID: 20260429_0001
Revises:
Create Date: 2026-04-29

本迁移建立第一阶段身份底座:
1. users: 内部用户主体；
2. local_accounts: 邮箱密码登录凭证；
3. wechat_accounts: 微信登录凭证；
4. email_verification_codes: 邮箱验证码；
5. positions / user_positions: 职务定义和用户职务关系。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260429_0001"
down_revision = None
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

    # --- 用户主体表 ---
    op.create_table(
        "users",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("display_name", sa.String(length=80), nullable=False),
        sa.Column("avatar_url", sa.String(length=512), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("last_login_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("remark", sa.Text(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_status", "users", ["status"])

    # --- 职务定义表 ---
    op.create_table(
        "positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_positions_code"),
    )
    op.create_index("ix_positions_status", "positions", ["status"])

    # 首批职务种子数据。998/999 是系统管理身份，不是日常业务审批角色。
    positions = sa.table(
        "positions",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("status", sa.String()),
        sa.column("sort_order", sa.Integer()),
        sa.column("is_system", sa.Boolean()),
    )
    op.bulk_insert(
        positions,
        [
            {
                "code": "member",
                "name": "干事",
                "status": "active",
                "sort_order": 10,
                "is_system": False,
            },
            {
                "code": "minister",
                "name": "部长",
                "status": "active",
                "sort_order": 20,
                "is_system": False,
            },
            {
                "code": "vice_president",
                "name": "副会长",
                "status": "active",
                "sort_order": 30,
                "is_system": False,
            },
            {
                "code": "president",
                "name": "会长",
                "status": "active",
                "sort_order": 40,
                "is_system": False,
            },
            {
                "code": "advisor",
                "name": "指导老师",
                "status": "active",
                "sort_order": 50,
                "is_system": False,
            },
            {
                "code": "998",
                "name": "管理员",
                "status": "active",
                "sort_order": 998,
                "is_system": True,
            },
            {
                "code": "999",
                "name": "超级管理员",
                "status": "active",
                "sort_order": 999,
                "is_system": True,
            },
        ],
    )

    # --- 本地账号表 ---
    op.create_table(
        "local_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("password_set_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_local_accounts_email"),
        sa.UniqueConstraint("user_id", name="uq_local_accounts_user_id"),
    )
    op.create_index("ix_local_accounts_status", "local_accounts", ["status"])
    op.create_index("ix_local_accounts_email_status", "local_accounts", ["email", "status"])

    # --- 微信账号表 ---
    op.create_table(
        "wechat_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("openid", sa.String(length=128), nullable=False),
        sa.Column("unionid", sa.String(length=128), nullable=True),
        sa.Column("session_key_hash", sa.String(length=255), nullable=True),
        sa.Column("bound_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("openid", name="uq_wechat_accounts_openid"),
        sa.UniqueConstraint("unionid", name="uq_wechat_accounts_unionid"),
        sa.UniqueConstraint("user_id", name="uq_wechat_accounts_user_id"),
    )
    op.create_index("ix_wechat_accounts_status", "wechat_accounts", ["status"])
    op.create_index("ix_wechat_accounts_openid_status", "wechat_accounts", ["openid", "status"])

    # --- 邮箱验证码表 ---
    op.create_table(
        "email_verification_codes",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("code_hash", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("consumed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("request_ip", sa.String(length=64), nullable=True),
        sa.Column("user_id", sa.BigInteger(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_email_verification_codes_email", "email_verification_codes", ["email"])
    op.create_index(
        "ix_email_verification_codes_email_purpose",
        "email_verification_codes",
        ["email", "purpose"],
    )
    op.create_index("ix_email_verification_codes_expires_at", "email_verification_codes", ["expires_at"])
    op.create_index("ix_email_verification_codes_purpose", "email_verification_codes", ["purpose"])
    op.create_index("ix_email_verification_codes_user_id", "email_verification_codes", ["user_id"])

    # --- 用户职务关系表 ---
    op.create_table(
        "user_positions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("position_id", sa.BigInteger(), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("scope_type", sa.String(length=32), server_default="global", nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=True),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_user_positions_position_id_revoked_at",
        "user_positions",
        ["position_id", "revoked_at"],
    )
    op.create_index(
        "ix_user_positions_user_id_revoked_at",
        "user_positions",
        ["user_id", "revoked_at"],
    )


def downgrade() -> None:
    """执行回滚迁移。"""

    # 回滚顺序必须先删除依赖表，再删除被依赖表。
    op.drop_index("ix_user_positions_user_id_revoked_at", table_name="user_positions")
    op.drop_index("ix_user_positions_position_id_revoked_at", table_name="user_positions")
    op.drop_table("user_positions")
    op.drop_index("ix_email_verification_codes_user_id", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_purpose", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_expires_at", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_email_purpose", table_name="email_verification_codes")
    op.drop_index("ix_email_verification_codes_email", table_name="email_verification_codes")
    op.drop_table("email_verification_codes")
    op.drop_index("ix_wechat_accounts_openid_status", table_name="wechat_accounts")
    op.drop_index("ix_wechat_accounts_status", table_name="wechat_accounts")
    op.drop_table("wechat_accounts")
    op.drop_index("ix_local_accounts_email_status", table_name="local_accounts")
    op.drop_index("ix_local_accounts_status", table_name="local_accounts")
    op.drop_table("local_accounts")
    op.drop_index("ix_positions_status", table_name="positions")
    op.drop_table("positions")
    op.drop_index("ix_users_status", table_name="users")
    op.drop_table("users")
