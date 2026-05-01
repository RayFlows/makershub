# migrations/versions/20260502_0006_align_system_operator_permissions.py
"""
对齐 998 与 999 的底层权限能力

Revision ID: 20260502_0006
Revises: 20260502_0005
Create Date: 2026-05-02

需求背景:
`998` 管理员与 `999` 超级管理员的底层能力一致，区别在于 `998` 必须由唯一
`999` 指定。上一版迁移把 `system_operator` 角色限制为运维权限子集，这会造成
998/999 能力不一致，因此用本迁移修正预置角色权限关系。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260502_0006"
down_revision = "20260502_0005"
branch_labels = None
depends_on = None

LEGACY_SYSTEM_OPERATOR_PERMISSIONS = [
    "system.admin.access",
    "system.audit.view",
    "system.permission.manage",
    "files.manage",
]


def clear_system_operator_permissions() -> None:
    """清空 system_operator 预置角色的权限关系。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'system_operator'
            )
            """,
        ),
    )


def insert_system_operator_permission(permission_code: str | None = None) -> None:
    """
    写入 system_operator 权限关系。

    Args:
        permission_code: 指定权限 code；为空时插入全部权限点。
    """

    if permission_code is None:
        op.execute(
            sa.text(
                """
                INSERT INTO role_permissions
                    (role_id, permission_id, created_at, updated_at)
                SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
                FROM roles r
                JOIN permissions p ON 1 = 1
                WHERE r.code = 'system_operator'
                """,
            ),
        )
        return

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions
                (role_id, permission_id, created_at, updated_at)
            SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r
            JOIN permissions p ON p.code = :permission_code
            WHERE r.code = 'system_operator'
            """,
        ).bindparams(permission_code=permission_code),
    )


def upgrade() -> None:
    """执行升级迁移。"""

    op.execute(
        sa.text(
            """
            UPDATE roles
            SET description = '998 管理由唯一 999 指定，底层能力与 999 一致。'
            WHERE code = 'system_operator'
            """,
        ),
    )
    clear_system_operator_permissions()
    insert_system_operator_permission()


def downgrade() -> None:
    """执行回滚迁移。"""

    op.execute(
        sa.text(
            """
            UPDATE roles
            SET description = '998 系统身份对应的运维权限，不包含日常业务审批权限。'
            WHERE code = 'system_operator'
            """,
        ),
    )
    clear_system_operator_permissions()
    for permission_code in LEGACY_SYSTEM_OPERATOR_PERMISSIONS:
        insert_system_operator_permission(permission_code)
