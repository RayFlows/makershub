# migrations/versions/20260512_0010_rename_account_and_role_grant_tables.py
"""
明确邮箱密码账号和用户角色授权记录表命名

需求背景:
`local_accounts` 容易被误解为“本地开发环境账号”，实际语义是系统自管的
邮箱密码登录凭证；`user_roles` 容易被误解为“用户权限表”，实际语义是
某个用户在某个作用域下被授予某个角色的授权记录。

本迁移只做命名收口，不改变业务数据、不改变登录链路，也不改变权限判断规则。
`role_permissions` 保持不变，它是 roles 与 permissions 的标准链接表。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = "20260512_0010"
down_revision = "20260512_0009"
branch_labels = None
depends_on = None


# --- 元数据检查工具 ---
def _table_exists(table_name: str) -> bool:
    """判断当前数据库中是否存在目标表。"""

    inspector = sa.inspect(op.get_bind())
    return table_name in inspector.get_table_names()


def _foreign_key_exists(table_name: str, constraint_name: str) -> bool:
    """判断表上是否存在指定外键约束。"""

    inspector = sa.inspect(op.get_bind())
    return any(item.get("name") == constraint_name for item in inspector.get_foreign_keys(table_name))


def _rename_table_if_needed(old_name: str, new_name: str) -> None:
    """幂等重命名表，方便本地重复修复或灾备演练时确认状态。"""

    if _table_exists(old_name) and not _table_exists(new_name):
        op.rename_table(old_name, new_name)


def _rename_mysql_index(table_name: str, old_name: str, new_name: str) -> None:
    """
    重命名 MySQL 索引。

    Alembic 没有跨方言的 rename index 操作；当前生产目标是 MySQL，因此只在
    MySQL 下执行。SQLite 测试库直接由 ORM metadata 创建，不依赖这段迁移。
    """

    bind = op.get_bind()
    if bind.dialect.name != "mysql":
        return
    index_count = bind.execute(
        sa.text(
            """
            SELECT COUNT(*)
              FROM information_schema.statistics
             WHERE table_schema = DATABASE()
               AND table_name = :table_name
               AND index_name = :index_name
            """,
        ),
        {"table_name": table_name, "index_name": old_name},
    ).scalar()
    if index_count:
        op.execute(sa.text(f"ALTER TABLE `{table_name}` RENAME INDEX `{old_name}` TO `{new_name}`"))


def _replace_foreign_key(
    table_name: str,
    *,
    old_name: str,
    new_name: str,
    local_columns: list[str],
    remote_table: str,
    remote_columns: list[str],
) -> None:
    """把外键约束名称同步成新表语义。"""

    bind = op.get_bind()
    if bind.dialect.name == "sqlite":
        return
    if _foreign_key_exists(table_name, old_name):
        op.drop_constraint(old_name, table_name, type_="foreignkey")
    if not _foreign_key_exists(table_name, new_name):
        op.create_foreign_key(
            new_name,
            table_name,
            remote_table,
            local_columns,
            remote_columns,
            ondelete="RESTRICT",
        )


# --- 升级与回滚 ---
def upgrade() -> None:
    """把旧命名表升级为更清楚的业务命名。"""

    _rename_table_if_needed("local_accounts", "email_password_accounts")
    _rename_mysql_index("email_password_accounts", "uq_local_accounts_email", "uq_email_password_accounts_email")
    _rename_mysql_index("email_password_accounts", "uq_local_accounts_user_id", "uq_email_password_accounts_user_id")
    _rename_mysql_index("email_password_accounts", "ix_local_accounts_status", "ix_email_password_accounts_status")
    _rename_mysql_index(
        "email_password_accounts",
        "ix_local_accounts_email_status",
        "ix_email_password_accounts_email_status",
    )
    _replace_foreign_key(
        "email_password_accounts",
        old_name="fk_local_accounts_user_id_users",
        new_name="fk_email_password_accounts_user_id_users",
        local_columns=["user_id"],
        remote_table="users",
        remote_columns=["id"],
    )

    _rename_table_if_needed("user_roles", "user_role_grants")
    _rename_mysql_index(
        "user_role_grants",
        "ix_user_roles_user_id_revoked_at",
        "ix_user_role_grants_user_id_revoked_at",
    )
    _rename_mysql_index(
        "user_role_grants",
        "ix_user_roles_role_id_revoked_at",
        "ix_user_role_grants_role_id_revoked_at",
    )
    _rename_mysql_index("user_role_grants", "ix_user_roles_scope", "ix_user_role_grants_scope")
    _replace_foreign_key(
        "user_role_grants",
        old_name="fk_user_roles_user_id_users",
        new_name="fk_user_role_grants_user_id_users",
        local_columns=["user_id"],
        remote_table="users",
        remote_columns=["id"],
    )
    _replace_foreign_key(
        "user_role_grants",
        old_name="fk_user_roles_role_id_roles",
        new_name="fk_user_role_grants_role_id_roles",
        local_columns=["role_id"],
        remote_table="roles",
        remote_columns=["id"],
    )
    _replace_foreign_key(
        "user_role_grants",
        old_name="fk_user_roles_granted_by_users",
        new_name="fk_user_role_grants_granted_by_users",
        local_columns=["granted_by"],
        remote_table="users",
        remote_columns=["id"],
    )


def downgrade() -> None:
    """回滚到旧表命名，便于紧急版本回退。"""

    _replace_foreign_key(
        "user_role_grants",
        old_name="fk_user_role_grants_user_id_users",
        new_name="fk_user_roles_user_id_users",
        local_columns=["user_id"],
        remote_table="users",
        remote_columns=["id"],
    )
    _replace_foreign_key(
        "user_role_grants",
        old_name="fk_user_role_grants_role_id_roles",
        new_name="fk_user_roles_role_id_roles",
        local_columns=["role_id"],
        remote_table="roles",
        remote_columns=["id"],
    )
    _replace_foreign_key(
        "user_role_grants",
        old_name="fk_user_role_grants_granted_by_users",
        new_name="fk_user_roles_granted_by_users",
        local_columns=["granted_by"],
        remote_table="users",
        remote_columns=["id"],
    )
    _rename_mysql_index("user_role_grants", "ix_user_role_grants_scope", "ix_user_roles_scope")
    _rename_mysql_index(
        "user_role_grants",
        "ix_user_role_grants_role_id_revoked_at",
        "ix_user_roles_role_id_revoked_at",
    )
    _rename_mysql_index(
        "user_role_grants",
        "ix_user_role_grants_user_id_revoked_at",
        "ix_user_roles_user_id_revoked_at",
    )
    _rename_table_if_needed("user_role_grants", "user_roles")

    _replace_foreign_key(
        "email_password_accounts",
        old_name="fk_email_password_accounts_user_id_users",
        new_name="fk_local_accounts_user_id_users",
        local_columns=["user_id"],
        remote_table="users",
        remote_columns=["id"],
    )
    _rename_mysql_index(
        "email_password_accounts",
        "ix_email_password_accounts_email_status",
        "ix_local_accounts_email_status",
    )
    _rename_mysql_index("email_password_accounts", "ix_email_password_accounts_status", "ix_local_accounts_status")
    _rename_mysql_index("email_password_accounts", "uq_email_password_accounts_user_id", "uq_local_accounts_user_id")
    _rename_mysql_index("email_password_accounts", "uq_email_password_accounts_email", "uq_local_accounts_email")
    _rename_table_if_needed("email_password_accounts", "local_accounts")
