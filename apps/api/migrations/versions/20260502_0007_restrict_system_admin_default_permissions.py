# migrations/versions/20260502_0007_restrict_system_admin_default_permissions.py
"""
收窄 998/999 默认权限到系统兜底能力

Revision ID: 20260502_0007
Revises: 20260502_0006
Create Date: 2026-05-02

需求背景:
999 是母账号，用于初始化、指定或恢复 998；998/999 属于底层管理身份，不应该
默认成为所有日常业务审批、查看或导出的角色。上一版迁移把 system_operator 设为
全部权限点，这会让普通业务权限被默认授予给 998/999。本迁移改为只授予系统兜底
权限，并新增 `system.operator.manage` 表达唯一 999 的指定管理员能力。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260502_0007"
down_revision = "20260502_0006"
branch_labels = None
depends_on = None

SYSTEM_ADMIN_PERMISSION_CODES = [
    "files.manage",
    "system.admin.access",
    "system.audit.view",
    "system.permission.manage",
]

SUPER_ADMIN_ONLY_PERMISSION_CODES = [
    "system.operator.manage",
    "system.super_admin.recover",
]


def insert_operator_manage_permission() -> None:
    """插入唯一 999 指定管理员权限点。"""

    op.execute(
        sa.text(
            """
            INSERT INTO permissions
                (code, name, module, description, risk_level, status, created_at, updated_at)
            SELECT
                'system.operator.manage',
                '指定或移除管理员',
                'system',
                '由唯一 999 指定或移除 998 管理员。',
                'critical',
                'active',
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM permissions WHERE code = 'system.operator.manage'
            )
            """,
        ),
    )


def clear_role_permissions(role_code: str) -> None:
    """清空指定预置角色的权限关系。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = :role_code
            )
            """,
        ).bindparams(role_code=role_code),
    )


def insert_role_permission(role_code: str, permission_code: str) -> None:
    """插入指定角色权限关系。"""

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions
                (role_id, permission_id, created_at, updated_at)
            SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r
            JOIN permissions p ON p.code = :permission_code
            WHERE r.code = :role_code
            """,
        ).bindparams(role_code=role_code, permission_code=permission_code),
    )


def insert_all_permissions_for_role(role_code: str) -> None:
    """把当前全部权限点授予指定角色，用于回滚到上一版行为。"""

    op.execute(
        sa.text(
            """
            INSERT INTO role_permissions
                (role_id, permission_id, created_at, updated_at)
            SELECT r.id, p.id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM roles r
            JOIN permissions p ON 1 = 1
            WHERE r.code = :role_code
            """,
        ).bindparams(role_code=role_code),
    )


def delete_operator_manage_permission() -> None:
    """删除本迁移新增的指定管理员权限点。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE permission_id IN (
                SELECT id FROM permissions WHERE code = 'system.operator.manage'
            )
            """,
        ),
    )
    op.execute(sa.text("DELETE FROM permissions WHERE code = 'system.operator.manage'"))


def upgrade() -> None:
    """执行升级迁移。"""

    insert_operator_manage_permission()
    op.execute(
        sa.text(
            """
            UPDATE roles
            SET description = '系统唯一 999 母账号，用于初始化、指定或恢复 998。'
            WHERE code = 'system_super_admin'
            """,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE roles
            SET description = '998 管理由唯一 999 指定，拥有系统兜底权限。'
            WHERE code = 'system_operator'
            """,
        ),
    )

    clear_role_permissions("system_super_admin")
    clear_role_permissions("system_operator")

    for permission_code in SYSTEM_ADMIN_PERMISSION_CODES:
        insert_role_permission("system_super_admin", permission_code)
        insert_role_permission("system_operator", permission_code)
    for permission_code in SUPER_ADMIN_ONLY_PERMISSION_CODES:
        insert_role_permission("system_super_admin", permission_code)


def downgrade() -> None:
    """执行回滚迁移。"""

    clear_role_permissions("system_super_admin")
    clear_role_permissions("system_operator")
    delete_operator_manage_permission()

    op.execute(
        sa.text(
            """
            UPDATE roles
            SET description = '系统唯一 999 兜底身份对应的完整权限集合。'
            WHERE code = 'system_super_admin'
            """,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE roles
            SET description = '998 管理由唯一 999 指定，底层能力与 999 一致。'
            WHERE code = 'system_operator'
            """,
        ),
    )

    insert_all_permissions_for_role("system_super_admin")
    insert_all_permissions_for_role("system_operator")
