# migrations/versions/20260511_0008_create_points_tables.py
"""
创建积分账户、冻结记录和积分流水表

Revision ID: 20260511_0008
Revises: 20260502_0007
Create Date: 2026-05-11

需求背景:
旧后端把积分放在 users.score 上，后台资料编辑可以直接覆盖数值，缺少冻结、流水、
幂等和审计边界。新版积分制度把积分作为协会内部货币处理：余额是缓存，流水是事实，
业务域只能通过 points 服务层追加流水。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260511_0008"
down_revision = "20260502_0007"
branch_labels = None
depends_on = None


POINT_PERMISSIONS = [
    {
        "code": "points.ledger.view",
        "name": "查看积分账本",
        "module": "points",
        "description": "查看成员积分账户和积分流水。",
        "risk_level": "high",
    },
    {
        "code": "points.manual.adjust",
        "name": "人工调整积分",
        "module": "points",
        "description": "受控人工补发或扣减积分，用于系统兜底和异常修复。",
        "risk_level": "critical",
    },
]


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


def insert_permission(permission: dict[str, str]) -> None:
    """幂等插入积分权限点。"""

    op.execute(
        sa.text(
            """
            INSERT INTO permissions
                (code, name, module, description, risk_level, status, created_at, updated_at)
            SELECT
                :code,
                :name,
                :module,
                :description,
                :risk_level,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE code = :code
            )
            """,
        ).bindparams(**permission),
    )


def insert_role(
    *,
    code: str,
    name: str,
    description: str,
    is_system: bool = True,
) -> None:
    """幂等插入预置角色。"""

    op.execute(
        sa.text(
            """
            INSERT INTO roles
                (code, name, description, is_system, status, created_at, updated_at)
            SELECT
                :code,
                :name,
                :description,
                :is_system,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM roles WHERE code = :code
            )
            """,
        ).bindparams(
            code=code,
            name=name,
            description=description,
            is_system=is_system,
        ),
    )


def insert_role_permission(role_code: str, permission_code: str) -> None:
    """幂等插入指定角色权限关系。"""

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions
                (role_id, permission_id, created_at, updated_at)
            SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r
            JOIN permissions p ON p.code = :permission_code
            WHERE r.code = :role_code
              AND NOT EXISTS (
                  SELECT 1
                  FROM role_permissions rp
                  WHERE rp.role_id = r.id
                    AND rp.permission_id = p.id
              )
            """,
        ).bindparams(role_code=role_code, permission_code=permission_code),
    )


def upgrade() -> None:
    """执行升级迁移。"""

    # --- 积分账户 ---
    op.create_table(
        "point_accounts",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("balance", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("frozen_balance", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("balance >= 0", name="ck_point_accounts_balance_non_negative"),
        sa.CheckConstraint(
            "frozen_balance >= 0",
            name="ck_point_accounts_frozen_balance_non_negative",
        ),
        sa.CheckConstraint(
            "frozen_balance <= balance",
            name="ck_point_accounts_frozen_not_greater_than_balance",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_point_accounts_user_id"),
    )
    op.create_index("ix_point_accounts_user_id", "point_accounts", ["user_id"])
    op.create_index("ix_point_accounts_status", "point_accounts", ["status"])

    # --- 积分冻结记录 ---
    op.create_table(
        "point_holds",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("business_type", sa.String(length=64), nullable=False),
        sa.Column("business_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("released_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deducted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("amount > 0", name="ck_point_holds_amount_positive"),
        sa.ForeignKeyConstraint(["account_id"], ["point_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_point_holds_idempotency_key"),
    )
    op.create_index("ix_point_holds_account_id", "point_holds", ["account_id"])
    op.create_index("ix_point_holds_user_id", "point_holds", ["user_id"])
    op.create_index("ix_point_holds_business_type", "point_holds", ["business_type"])
    op.create_index("ix_point_holds_business_id", "point_holds", ["business_id"])
    op.create_index("ix_point_holds_status", "point_holds", ["status"])
    op.create_index("ix_point_holds_user_status", "point_holds", ["user_id", "status"])
    op.create_index("ix_point_holds_business", "point_holds", ["business_type", "business_id"])

    # --- 积分流水 ---
    op.create_table(
        "point_ledger_entries",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("account_id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("direction", sa.String(length=32), nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("balance_after", sa.BigInteger(), nullable=False),
        sa.Column("available_balance_after", sa.BigInteger(), nullable=False),
        sa.Column("frozen_balance_after", sa.BigInteger(), nullable=False),
        sa.Column("business_type", sa.String(length=64), nullable=False),
        sa.Column("business_id", sa.String(length=128), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column("related_hold_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("operator_id", sa.BigInteger(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_point_ledger_entries_amount_positive"),
        sa.ForeignKeyConstraint(["account_id"], ["point_accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["related_hold_id"], ["point_holds.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idempotency_key", name="uq_point_ledger_entries_idempotency_key"),
    )
    op.create_index("ix_point_ledger_entries_account_id", "point_ledger_entries", ["account_id"])
    op.create_index("ix_point_ledger_entries_user_id", "point_ledger_entries", ["user_id"])
    op.create_index("ix_point_ledger_entries_direction", "point_ledger_entries", ["direction"])
    op.create_index("ix_point_ledger_entries_business_type", "point_ledger_entries", ["business_type"])
    op.create_index("ix_point_ledger_entries_business_id", "point_ledger_entries", ["business_id"])
    op.create_index("ix_point_ledger_entries_related_hold_id", "point_ledger_entries", ["related_hold_id"])
    op.create_index("ix_point_ledger_entries_operator_id", "point_ledger_entries", ["operator_id"])
    op.create_index("ix_point_ledger_entries_created_at", "point_ledger_entries", ["created_at"])
    op.create_index(
        "ix_point_ledger_entries_user_created",
        "point_ledger_entries",
        ["user_id", "created_at"],
    )
    op.create_index(
        "ix_point_ledger_entries_business",
        "point_ledger_entries",
        ["business_type", "business_id"],
    )

    # --- 旧用户补齐 0 积分账户 ---
    op.execute(
        sa.text(
            """
            INSERT INTO point_accounts
                (user_id, balance, frozen_balance, status, created_at, updated_at)
            SELECT u.id, 0, 0, 'active', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM users u
            WHERE NOT EXISTS (
                SELECT 1 FROM point_accounts pa WHERE pa.user_id = u.id
            )
            """,
        ),
    )

    # --- 权限点和预置角色 ---
    for permission in POINT_PERMISSIONS:
        insert_permission(permission)

    insert_role(
        code="points_manager",
        name="积分账本查看员",
        description="查看成员积分账户和积分流水，不包含人工调整积分能力。",
    )
    insert_role_permission("points_manager", "system.admin.access")
    insert_role_permission("points_manager", "points.ledger.view")
    insert_role_permission("system_super_admin", "points.manual.adjust")
    insert_role_permission("system_operator", "points.manual.adjust")


def downgrade() -> None:
    """执行回滚迁移。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions
                WHERE code IN ('points.ledger.view', 'points.manual.adjust')
            )
               OR role_id IN (
                SELECT id FROM roles WHERE code = 'points_manager'
            )
            """,
        ),
    )
    op.execute(
        sa.text(
            """
            DELETE FROM user_roles
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'points_manager'
            )
            """,
        ),
    )
    op.execute(sa.text("DELETE FROM roles WHERE code = 'points_manager'"))
    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN ('points.ledger.view', 'points.manual.adjust')
            """,
        ),
    )

    op.drop_index("ix_point_ledger_entries_business", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_user_created", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_created_at", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_operator_id", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_related_hold_id", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_business_id", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_business_type", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_direction", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_user_id", table_name="point_ledger_entries")
    op.drop_index("ix_point_ledger_entries_account_id", table_name="point_ledger_entries")
    op.drop_table("point_ledger_entries")

    op.drop_index("ix_point_holds_business", table_name="point_holds")
    op.drop_index("ix_point_holds_user_status", table_name="point_holds")
    op.drop_index("ix_point_holds_status", table_name="point_holds")
    op.drop_index("ix_point_holds_business_id", table_name="point_holds")
    op.drop_index("ix_point_holds_business_type", table_name="point_holds")
    op.drop_index("ix_point_holds_user_id", table_name="point_holds")
    op.drop_index("ix_point_holds_account_id", table_name="point_holds")
    op.drop_table("point_holds")

    op.drop_index("ix_point_accounts_status", table_name="point_accounts")
    op.drop_index("ix_point_accounts_user_id", table_name="point_accounts")
    op.drop_table("point_accounts")
