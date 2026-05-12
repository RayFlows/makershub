# migrations/versions/20260512_0011_create_point_rule_tables.py
"""
创建积分规则和临时积分规则审批表

Revision ID: 20260512_0011
Revises: 20260512_0010
Create Date: 2026-05-12

需求背景:
旧系统只有 users.score，后台可以直接改分，没有固定规则、临时规则审批、一次性任务
模板和反向修正链路。新版积分域必须把“按规则自动发放”和“系统兜底人工调整”分开：
日常规则由业务角色审批，998/999 只保留异常修复能力。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0011"
down_revision = "20260512_0010"
branch_labels = None
depends_on = None


POINT_RULE_PERMISSIONS = [
    {
        "code": "points.rule.view",
        "name": "查看积分规则",
        "module": "points",
        "description": "查看固定积分规则、临时规则申请和一次性任务模板。",
        "risk_level": "medium",
    },
    {
        "code": "points.rule.manage",
        "name": "维护固定积分规则",
        "module": "points",
        "description": "创建或撤回固定积分规则，不包含系统兜底人工改分。",
        "risk_level": "high",
    },
    {
        "code": "points.temporary_rule.apply",
        "name": "提交临时积分规则",
        "module": "points",
        "description": "为特殊非模板任务提交临时积分规则申请。",
        "risk_level": "medium",
    },
    {
        "code": "points.temporary_rule.review",
        "name": "审批临时积分规则",
        "module": "points",
        "description": "审批、驳回或撤回临时积分规则，并生成一次性任务模板。",
        "risk_level": "high",
    },
]


ROLE_DEFINITIONS = [
    {
        "code": "points_rule_applicant",
        "name": "临时积分规则申请人",
        "description": "提交特殊非模板任务的临时积分规则申请。",
        "permissions": [
            "system.admin.access",
            "points.rule.view",
            "points.temporary_rule.apply",
        ],
    },
    {
        "code": "points_rule_reviewer",
        "name": "临时积分规则审批员",
        "description": "审批、驳回和撤回临时积分规则，不包含系统兜底人工改分。",
        "permissions": [
            "system.admin.access",
            "points.ledger.view",
            "points.rule.view",
            "points.temporary_rule.review",
        ],
    },
    {
        "code": "points_rule_manager",
        "name": "积分规则管理员",
        "description": "维护固定积分规则，并处理临时积分规则申请和审批。",
        "permissions": [
            "system.admin.access",
            "points.ledger.view",
            "points.rule.view",
            "points.rule.manage",
            "points.temporary_rule.apply",
            "points.temporary_rule.review",
        ],
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
    """幂等插入积分规则权限点。"""

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


def insert_role(*, code: str, name: str, description: str) -> None:
    """幂等插入预置积分规则角色。"""

    op.execute(
        sa.text(
            """
            INSERT INTO roles
                (code, name, description, is_system, status, created_at, updated_at)
            SELECT
                :code,
                :name,
                :description,
                TRUE,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM roles WHERE code = :code
            )
            """,
        ).bindparams(code=code, name=name, description=description),
    )


def insert_role_permission(role_code: str, permission_code: str) -> None:
    """幂等插入角色权限关系。"""

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

    # --- 固定规则和一次性任务模板 ---
    op.create_table(
        "point_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("rule_type", sa.String(length=40), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.Column("amount", sa.BigInteger(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("amount > 0", name="ck_point_rules_amount_positive"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_point_rules_code"),
    )
    op.create_index("ix_point_rules_code", "point_rules", ["code"])
    op.create_index("ix_point_rules_rule_type", "point_rules", ["rule_type"])
    op.create_index("ix_point_rules_status", "point_rules", ["status"])
    op.create_index("ix_point_rules_created_by", "point_rules", ["created_by"])
    op.create_index("ix_point_rules_updated_by", "point_rules", ["updated_by"])
    op.create_index("ix_point_rules_type_status", "point_rules", ["rule_type", "status"])
    op.create_index(
        "ix_point_rules_effective_window",
        "point_rules",
        ["effective_from", "effective_to"],
    )

    # --- 临时规则申请和审批状态 ---
    op.create_table(
        "temporary_point_rules",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("target_scope", sa.String(length=64), server_default="members", nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("completion_requirements", sa.Text(), nullable=True),
        sa.Column("amount_per_completion", sa.BigInteger(), nullable=False),
        sa.Column("max_participants", sa.Integer(), nullable=False),
        sa.Column("total_points_limit", sa.BigInteger(), nullable=False),
        sa.Column("effective_from", sa.DateTime(timezone=True), nullable=False),
        sa.Column("effective_to", sa.DateTime(timezone=True), nullable=False),
        sa.Column("approval_status", sa.String(length=32), server_default="pending", nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("approved_by", sa.BigInteger(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("approval_reason", sa.Text(), nullable=True),
        sa.Column("rejected_by", sa.BigInteger(), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_reason", sa.Text(), nullable=True),
        sa.Column("generated_point_rule_id", sa.BigInteger(), nullable=True),
        sa.Column("revoke_status", sa.String(length=32), server_default="none", nullable=False),
        sa.Column("revoked_by", sa.BigInteger(), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoke_reason", sa.Text(), nullable=True),
        sa.Column("revoke_impact_note", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint(
            "amount_per_completion > 0",
            name="ck_temporary_point_rules_amount_positive",
        ),
        sa.CheckConstraint(
            "max_participants > 0",
            name="ck_temporary_point_rules_max_participants_positive",
        ),
        sa.CheckConstraint(
            "total_points_limit > 0",
            name="ck_temporary_point_rules_total_limit_positive",
        ),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["approved_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["generated_point_rule_id"], ["point_rules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["rejected_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["revoked_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_temporary_point_rules_department_id", "temporary_point_rules", ["department_id"])
    op.create_index("ix_temporary_point_rules_approval_status", "temporary_point_rules", ["approval_status"])
    op.create_index("ix_temporary_point_rules_applicant_id", "temporary_point_rules", ["applicant_id"])
    op.create_index("ix_temporary_point_rules_approved_by", "temporary_point_rules", ["approved_by"])
    op.create_index("ix_temporary_point_rules_rejected_by", "temporary_point_rules", ["rejected_by"])
    op.create_index("ix_temporary_point_rules_revoked_by", "temporary_point_rules", ["revoked_by"])
    op.create_index(
        "ix_temporary_point_rules_generated_point_rule_id",
        "temporary_point_rules",
        ["generated_point_rule_id"],
    )
    op.create_index("ix_temporary_point_rules_revoke_status", "temporary_point_rules", ["revoke_status"])
    op.create_index(
        "ix_temporary_point_rules_status",
        "temporary_point_rules",
        ["approval_status", "revoke_status"],
    )
    op.create_index(
        "ix_temporary_point_rules_applicant_status",
        "temporary_point_rules",
        ["applicant_id", "approval_status"],
    )
    op.create_index(
        "ix_temporary_point_rules_effective_window",
        "temporary_point_rules",
        ["effective_from", "effective_to"],
    )

    # --- 临时规则生命周期事件 ---
    op.create_table(
        "temporary_point_rule_events",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("temporary_rule_id", sa.BigInteger(), nullable=False),
        sa.Column("event_type", sa.String(length=40), nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["temporary_rule_id"], ["temporary_point_rules.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_temporary_point_rule_events_temporary_rule_id",
        "temporary_point_rule_events",
        ["temporary_rule_id"],
    )
    op.create_index("ix_temporary_point_rule_events_event_type", "temporary_point_rule_events", ["event_type"])
    op.create_index("ix_temporary_point_rule_events_actor_id", "temporary_point_rule_events", ["actor_id"])
    op.create_index("ix_temporary_point_rule_events_created_at", "temporary_point_rule_events", ["created_at"])
    op.create_index(
        "ix_temporary_point_rule_events_rule_created",
        "temporary_point_rule_events",
        ["temporary_rule_id", "created_at"],
    )

    # --- 权限点和预置角色 ---
    for permission in POINT_RULE_PERMISSIONS:
        insert_permission(permission)
    for role in ROLE_DEFINITIONS:
        insert_role(code=role["code"], name=role["name"], description=role["description"])
        for permission_code in role["permissions"]:
            insert_role_permission(role["code"], permission_code)


def downgrade() -> None:
    """执行回滚迁移。"""

    role_codes = tuple(role["code"] for role in ROLE_DEFINITIONS)
    permission_codes = tuple(permission["code"] for permission in POINT_RULE_PERMISSIONS)

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE code IN :role_codes
            )
               OR permission_id IN (
                SELECT id FROM permissions WHERE code IN :permission_codes
            )
            """,
        ).bindparams(
            sa.bindparam("role_codes", expanding=True, value=role_codes),
            sa.bindparam("permission_codes", expanding=True, value=permission_codes),
        ),
    )
    op.execute(
        sa.text(
            """
            DELETE FROM user_role_grants
            WHERE role_id IN (
                SELECT id FROM roles WHERE code IN :role_codes
            )
            """,
        ).bindparams(sa.bindparam("role_codes", expanding=True, value=role_codes)),
    )
    op.execute(
        sa.text("DELETE FROM roles WHERE code IN :role_codes").bindparams(
            sa.bindparam("role_codes", expanding=True, value=role_codes),
        ),
    )
    op.execute(
        sa.text("DELETE FROM permissions WHERE code IN :permission_codes").bindparams(
            sa.bindparam("permission_codes", expanding=True, value=permission_codes),
        ),
    )

    op.drop_index("ix_temporary_point_rule_events_rule_created", table_name="temporary_point_rule_events")
    op.drop_index("ix_temporary_point_rule_events_created_at", table_name="temporary_point_rule_events")
    op.drop_index("ix_temporary_point_rule_events_actor_id", table_name="temporary_point_rule_events")
    op.drop_index("ix_temporary_point_rule_events_event_type", table_name="temporary_point_rule_events")
    op.drop_index(
        "ix_temporary_point_rule_events_temporary_rule_id",
        table_name="temporary_point_rule_events",
    )
    op.drop_table("temporary_point_rule_events")

    op.drop_index("ix_temporary_point_rules_effective_window", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_applicant_status", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_status", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_revoke_status", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_generated_point_rule_id", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_revoked_by", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_rejected_by", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_approved_by", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_applicant_id", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_approval_status", table_name="temporary_point_rules")
    op.drop_index("ix_temporary_point_rules_department_id", table_name="temporary_point_rules")
    op.drop_table("temporary_point_rules")

    op.drop_index("ix_point_rules_effective_window", table_name="point_rules")
    op.drop_index("ix_point_rules_type_status", table_name="point_rules")
    op.drop_index("ix_point_rules_updated_by", table_name="point_rules")
    op.drop_index("ix_point_rules_created_by", table_name="point_rules")
    op.drop_index("ix_point_rules_status", table_name="point_rules")
    op.drop_index("ix_point_rules_rule_type", table_name="point_rules")
    op.drop_index("ix_point_rules_code", table_name="point_rules")
    op.drop_table("point_rules")
