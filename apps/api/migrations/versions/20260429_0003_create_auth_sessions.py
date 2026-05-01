# migrations/versions/20260429_0003_create_auth_sessions.py
"""
创建登录会话表

Revision ID: 20260429_0003
Revises: 20260429_0002
Create Date: 2026-04-29

需求背景:
网页端和后台管理端需要短期 access token + 长期 refresh token 的双令牌机制；
小程序虽然可以通过 wx.login 静默重登，也应该复用同一套会话撤销能力。
refresh token 只保存哈希值，避免数据库泄露后长期凭证直接可用。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260429_0003"
down_revision = "20260429_0002"
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

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("refresh_token_hash", sa.String(length=128), nullable=False),
        sa.Column("channel", sa.String(length=32), nullable=False),
        sa.Column("client_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.String(length=255), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("refresh_token_hash", name="uq_auth_sessions_refresh_token_hash"),
    )
    op.create_index("ix_auth_sessions_expires_at", "auth_sessions", ["expires_at"])
    op.create_index("ix_auth_sessions_status", "auth_sessions", ["status"])
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"])
    op.create_index(
        "ix_auth_sessions_user_id_status",
        "auth_sessions",
        ["user_id", "status"],
    )
    op.create_index(
        "ix_auth_sessions_refresh_token_hash_status",
        "auth_sessions",
        ["refresh_token_hash", "status"],
    )


def downgrade() -> None:
    """执行回滚迁移。"""

    op.drop_index("ix_auth_sessions_refresh_token_hash_status", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id_status", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_user_id", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_status", table_name="auth_sessions")
    op.drop_index("ix_auth_sessions_expires_at", table_name="auth_sessions")
    op.drop_table("auth_sessions")
