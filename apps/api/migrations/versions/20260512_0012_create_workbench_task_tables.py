# migrations/versions/20260512_0012_create_workbench_task_tables.py
"""
创建工作台任务表

Revision ID: 20260512_0012
Revises: 20260512_0011
Create Date: 2026-05-12

需求背景:
旧任务模块只有“未完成/已完成/已取消”，执行人可以直接把任务标记完成。新版需求要求
任务完成拆成“执行人提交材料”和“发布人审核”，并且任务积分必须引用已有积分规则，
审核通过后通过积分账本发放，不能在任务表里直接写分。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0012"
down_revision = "20260512_0011"
branch_labels = None
depends_on = None


WORKBENCH_PERMISSIONS = [
    {
        "code": "workbench.task.publish",
        "name": "发布工作台任务",
        "module": "workbench",
        "description": "发布指定任务或悬赏任务，任务积分必须引用已有积分规则。",
        "risk_level": "medium",
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
    """幂等插入工作台权限点。"""

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


def insert_workbench_role() -> None:
    """幂等插入工作台任务发布角色。"""

    op.execute(
        sa.text(
            """
            INSERT INTO roles
                (code, name, description, is_system, status, created_at, updated_at)
            SELECT
                'workbench_task_publisher',
                '工作台任务发布人',
                '发布指定任务和悬赏任务，审核自己发布任务的完成结果。',
                TRUE,
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM roles WHERE code = 'workbench_task_publisher'
            )
            """,
        ),
    )


def upgrade() -> None:
    """执行升级迁移。"""

    # --- 工作台任务 ---
    op.create_table(
        "workbench_tasks",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("title", sa.String(length=120), nullable=False),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("assignment_type", sa.String(length=32), nullable=False),
        sa.Column("visibility", sa.String(length=32), nullable=False),
        sa.Column("department_id", sa.BigInteger(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("deadline", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("publisher_id", sa.BigInteger(), nullable=False),
        sa.Column("assignee_id", sa.BigInteger(), nullable=True),
        sa.Column("claimed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("point_rule_id", sa.BigInteger(), nullable=False),
        sa.Column("submission_content", sa.Text(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by", sa.BigInteger(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("point_ledger_entry_id", sa.BigInteger(), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["assignee_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["department_id"], ["departments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["point_ledger_entry_id"], ["point_ledger_entries.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["point_rule_id"], ["point_rules.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["publisher_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_workbench_tasks_task_type", "workbench_tasks", ["task_type"])
    op.create_index("ix_workbench_tasks_assignment_type", "workbench_tasks", ["assignment_type"])
    op.create_index("ix_workbench_tasks_visibility", "workbench_tasks", ["visibility"])
    op.create_index("ix_workbench_tasks_department_id", "workbench_tasks", ["department_id"])
    op.create_index("ix_workbench_tasks_deadline", "workbench_tasks", ["deadline"])
    op.create_index("ix_workbench_tasks_status", "workbench_tasks", ["status"])
    op.create_index("ix_workbench_tasks_publisher_id", "workbench_tasks", ["publisher_id"])
    op.create_index("ix_workbench_tasks_assignee_id", "workbench_tasks", ["assignee_id"])
    op.create_index("ix_workbench_tasks_point_rule_id", "workbench_tasks", ["point_rule_id"])
    op.create_index("ix_workbench_tasks_reviewed_by", "workbench_tasks", ["reviewed_by"])
    op.create_index(
        "ix_workbench_tasks_point_ledger_entry_id",
        "workbench_tasks",
        ["point_ledger_entry_id"],
    )
    op.create_index("ix_workbench_tasks_status_created", "workbench_tasks", ["status", "created_at"])
    op.create_index("ix_workbench_tasks_assignee_status", "workbench_tasks", ["assignee_id", "status"])
    op.create_index("ix_workbench_tasks_publisher_status", "workbench_tasks", ["publisher_id", "status"])
    op.create_index("ix_workbench_tasks_visibility_status", "workbench_tasks", ["visibility", "status"])

    # --- 权限点和预置角色 ---
    for permission in WORKBENCH_PERMISSIONS:
        insert_permission(permission)
    insert_workbench_role()
    insert_role_permission("workbench_task_publisher", "system.admin.access")
    insert_role_permission("workbench_task_publisher", "workbench.task.publish")


def downgrade() -> None:
    """执行回滚迁移。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'workbench_task_publisher'
            )
               OR permission_id IN (
                SELECT id FROM permissions WHERE code = 'workbench.task.publish'
            )
            """,
        ),
    )
    op.execute(
        sa.text(
            """
            DELETE FROM user_role_grants
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'workbench_task_publisher'
            )
            """,
        ),
    )
    op.execute(sa.text("DELETE FROM roles WHERE code = 'workbench_task_publisher'"))
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'workbench.task.publish'"))

    op.drop_index("ix_workbench_tasks_visibility_status", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_publisher_status", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_assignee_status", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_status_created", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_point_ledger_entry_id", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_reviewed_by", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_point_rule_id", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_assignee_id", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_publisher_id", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_status", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_deadline", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_department_id", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_visibility", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_assignment_type", table_name="workbench_tasks")
    op.drop_index("ix_workbench_tasks_task_type", table_name="workbench_tasks")
    op.drop_table("workbench_tasks")
