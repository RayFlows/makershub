# migrations/versions/20260512_0009_align_position_codes.py
"""
对齐协会身份与职务代码

Revision ID: 20260512_0009
Revises: 20260511_0008
Create Date: 2026-05-12

需求背景:
需求文档已经确认协会身份使用 `0/1/2/3/4/5/998/999` 这组稳定代码。早期迁移
曾使用 member、minister 等英文 code，真实数据库和接口测试会产生漂移。本迁移把
普通协会身份和职务统一改为数字代码，并补齐 `0` 外部成员/协会会员基础身份。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0009"
down_revision = "20260511_0008"
branch_labels = None
depends_on = None

POSITION_CODE_MAPPINGS = [
    ("member", "1", "干事", 10),
    ("minister", "2", "部长", 20),
    ("vice_president", "3", "副会长", 30),
    ("president", "4", "会长", 40),
    ("advisor", "5", "指导老师", 50),
]


def rename_position_code(
    *,
    old_code: str,
    new_code: str,
    name: str,
    sort_order: int,
) -> None:
    """把早期英文职务代码改成需求文档确认的数字代码。"""

    op.execute(
        sa.text(
            """
            UPDATE positions
            SET code = :new_code,
                name = :name,
                sort_order = :sort_order,
                is_system = 0,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            WHERE code = :old_code
              AND NOT EXISTS (
                  SELECT 1 FROM (
                      SELECT id FROM positions WHERE code = :new_code
                  ) AS existing_position
              )
            """,
        ).bindparams(
            old_code=old_code,
            new_code=new_code,
            name=name,
            sort_order=sort_order,
        ),
    )
    op.execute(
        sa.text(
            """
            UPDATE positions
            SET name = :name,
                sort_order = :sort_order,
                is_system = 0,
                status = 'active',
                updated_at = CURRENT_TIMESTAMP
            WHERE code = :new_code
            """,
        ).bindparams(new_code=new_code, name=name, sort_order=sort_order),
    )


def insert_position_if_missing(
    *,
    code: str,
    name: str,
    sort_order: int,
    is_system: bool = False,
) -> None:
    """幂等插入职务定义。"""

    op.execute(
        sa.text(
            """
            INSERT INTO positions
                (code, name, status, sort_order, is_system, created_at, updated_at)
            SELECT
                :code,
                :name,
                'active',
                :sort_order,
                :is_system,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            WHERE NOT EXISTS (
                SELECT 1 FROM positions WHERE code = :code
            )
            """,
        ).bindparams(
            code=code,
            name=name,
            sort_order=sort_order,
            is_system=is_system,
        ),
    )


def grant_external_member_to_unclassified_users() -> None:
    """
    给没有普通协会职务的存量用户补齐 0 基础身份。

    这不会授予后台权限，只是把“已经在系统内但还不是干事”的用户明确标记为
    外部成员/协会会员，便于后续公开任务和积分规则判断。
    """

    op.execute(
        sa.text(
            """
            INSERT INTO user_positions
                (
                    user_id,
                    position_id,
                    department_id,
                    scope_type,
                    scope_id,
                    granted_by,
                    granted_at,
                    created_at,
                    updated_at
                )
            SELECT
                u.id,
                p.id,
                NULL,
                'global',
                NULL,
                NULL,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP,
                CURRENT_TIMESTAMP
            FROM users u
            JOIN positions p ON p.code = '0'
            WHERE u.deleted_at IS NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM user_positions up
                  JOIN positions existing_position ON existing_position.id = up.position_id
                  WHERE up.user_id = u.id
                    AND up.revoked_at IS NULL
                    AND existing_position.is_system = 0
              )
            """,
        ),
    )


def upgrade() -> None:
    """执行升级迁移。"""

    insert_position_if_missing(code="0", name="外部成员", sort_order=0)
    for old_code, new_code, name, sort_order in POSITION_CODE_MAPPINGS:
        rename_position_code(
            old_code=old_code,
            new_code=new_code,
            name=name,
            sort_order=sort_order,
        )
    grant_external_member_to_unclassified_users()


def downgrade() -> None:
    """执行回滚迁移。"""

    op.execute(
        sa.text(
            """
            DELETE FROM user_positions
            WHERE position_id IN (
                SELECT id FROM positions WHERE code = '0'
            )
            """,
        ),
    )
    op.execute(sa.text("DELETE FROM positions WHERE code = '0'"))

    for old_code, new_code, name, sort_order in POSITION_CODE_MAPPINGS:
        op.execute(
            sa.text(
                """
                UPDATE positions
                SET code = :old_code,
                    name = :name,
                    sort_order = :sort_order,
                    is_system = 0,
                    status = 'active',
                    updated_at = CURRENT_TIMESTAMP
                WHERE code = :new_code
                  AND NOT EXISTS (
                      SELECT 1 FROM (
                          SELECT id FROM positions WHERE code = :old_code
                      ) AS existing_position
                  )
                """,
            ).bindparams(
                old_code=old_code,
                new_code=new_code,
                name=name,
                sort_order=sort_order,
            ),
        )
