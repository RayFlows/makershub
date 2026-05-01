# migrations/versions/20260429_0002_allow_pending_local_account_password.py
"""
允许本地账号处于待设置密码状态

Revision ID: 20260429_0002
Revises: 20260429_0001
Create Date: 2026-04-29

需求背景:
普通用户第一版必须先通过小程序微信登录建立用户主体，再绑定邮箱；
网页端首次登录时才设置密码。因此 local_accounts 需要支持
“邮箱已验证但 password_hash 为空”的状态。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260429_0002"
down_revision = "20260429_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """允许 password_hash 为空。"""

    op.alter_column(
        "local_accounts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=True,
    )


def downgrade() -> None:
    """
    回滚为 password_hash 非空。

    注意:
        如果数据库中已经存在待设置密码账号，回滚前需要填入不可用占位哈希，
        否则数据库会因为 NULL 值拒绝改回 NOT NULL。
    """

    op.execute(
        "UPDATE local_accounts "
        "SET password_hash = '__pending_password_not_usable__' "
        "WHERE password_hash IS NULL"
    )
    op.alter_column(
        "local_accounts",
        "password_hash",
        existing_type=sa.String(length=255),
        nullable=False,
    )
