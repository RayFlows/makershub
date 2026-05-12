# migrations/versions/20260512_0013_allow_task_publishers_view_point_rules.py
"""
允许工作台任务发布人查看积分规则

Revision ID: 20260512_0013
Revises: 20260512_0012
Create Date: 2026-05-12

需求背景:
工作台任务发布时必须引用已有积分规则。仅授予 `workbench.task.publish` 会导致前端无法
自然展示可选规则，只能让发布人手填规则 ID，不符合可维护的端到端业务流程。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0013"
down_revision = "20260512_0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """把积分规则查看权限补给工作台任务发布角色。"""

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions
                (role_id, permission_id, created_at, updated_at)
            SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r
            JOIN permissions p ON p.code = 'points.rule.view'
            WHERE r.code = 'workbench_task_publisher'
              AND NOT EXISTS (
                  SELECT 1
                  FROM role_permissions rp
                  WHERE rp.role_id = r.id
                    AND rp.permission_id = p.id
              )
            """,
        ),
    )


def downgrade() -> None:
    """回滚工作台任务发布角色的积分规则查看权限。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'workbench_task_publisher'
            )
              AND permission_id IN (
                SELECT id FROM permissions WHERE code = 'points.rule.view'
            )
            """,
        ),
    )
