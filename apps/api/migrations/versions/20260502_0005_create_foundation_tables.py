# migrations/versions/20260502_0005_create_foundation_tables.py
"""
创建权限、审计与文件元数据基础表

Revision ID: 20260502_0005
Revises: 20260502_0004
Create Date: 2026-05-02

需求背景:
重构不能继续用旧系统的 role 数字比较和散落日志支撑长期维护。第一阶段在继续业务功能
前先补齐权限点、角色授权、审计日志和统一文件元数据，为后台管理、积分、资源借用、
项目材料上传等模块提供稳定底座。
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260502_0005"
down_revision = "20260502_0004"
branch_labels = None
depends_on = None


CORE_PERMISSIONS = [
    {
        "code": "system.admin.access",
        "name": "访问后台管理端",
        "module": "system",
        "description": "允许进入后台管理端框架，具体菜单仍需业务权限控制。",
        "risk_level": "medium",
        "status": "active",
    },
    {
        "code": "system.audit.view",
        "name": "查看审计日志",
        "module": "audit",
        "description": "查看系统审计日志和高风险操作记录。",
        "risk_level": "high",
        "status": "active",
    },
    {
        "code": "system.permission.manage",
        "name": "维护权限与角色",
        "module": "system",
        "description": "维护系统权限、角色和用户授权关系。",
        "risk_level": "critical",
        "status": "active",
    },
    {
        "code": "organization.member.manage",
        "name": "维护成员资料",
        "module": "organization",
        "description": "维护他人成员资料，不包含系统登录凭证和积分余额。",
        "risk_level": "medium",
        "status": "active",
    },
    {
        "code": "organization.department.manage",
        "name": "维护部门归属",
        "module": "organization",
        "description": "调整成员部门关系和部门基础信息。",
        "risk_level": "high",
        "status": "active",
    },
    {
        "code": "organization.position.manage",
        "name": "维护职务身份",
        "module": "organization",
        "description": "授予或撤销部长、副会长、会长、指导老师等职务身份。",
        "risk_level": "high",
        "status": "active",
    },
    {
        "code": "system.super_admin.recover",
        "name": "灾备恢复超级管理员",
        "module": "system",
        "description": "受控恢复唯一 999 超级管理员，只能由运维脚本或灾备流程触发。",
        "risk_level": "critical",
        "status": "active",
    },
    {
        "code": "files.upload",
        "name": "上传文件",
        "module": "files",
        "description": "允许通过统一文件接口上传业务文件。",
        "risk_level": "medium",
        "status": "active",
    },
    {
        "code": "files.manage",
        "name": "维护文件元数据",
        "module": "files",
        "description": "维护文件元数据、状态和存储对象引用。",
        "risk_level": "high",
        "status": "active",
    },
]

SYSTEM_OPERATOR_PERMISSIONS = [
    "system.admin.access",
    "system.audit.view",
    "system.permission.manage",
    "files.manage",
]

ORGANIZATION_MANAGER_PERMISSIONS = [
    "system.admin.access",
    "organization.member.manage",
    "organization.department.manage",
    "organization.position.manage",
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


def insert_role_permission(role_code: str, permission_code: str) -> None:
    """为预置角色插入权限关系。"""

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


def upgrade() -> None:
    """执行升级迁移。"""

    # --- 权限点表 ---
    op.create_table(
        "permissions",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("module", sa.String(length=64), nullable=False),
        sa.Column("risk_level", sa.String(length=32), server_default="low", nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_permissions_code"),
    )
    op.create_index("ix_permissions_module", "permissions", ["module"])
    op.create_index("ix_permissions_risk_level", "permissions", ["risk_level"])
    op.create_index("ix_permissions_status", "permissions", ["status"])

    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("module", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("risk_level", sa.String()),
        sa.column("status", sa.String()),
    )
    op.bulk_insert(permissions_table, CORE_PERMISSIONS)

    # --- 角色表 ---
    op.create_table(
        "roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("code", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_system", sa.Boolean(), server_default=sa.text("0"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_roles_code"),
    )
    op.create_index("ix_roles_status", "roles", ["status"])

    roles_table = sa.table(
        "roles",
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("description", sa.Text()),
        sa.column("is_system", sa.Boolean()),
        sa.column("status", sa.String()),
    )
    op.bulk_insert(
        roles_table,
        [
            {
                "code": "system_super_admin",
                "name": "超级管理员",
                "description": "系统唯一 999 兜底身份对应的完整权限集合。",
                "is_system": True,
                "status": "active",
            },
            {
                "code": "system_operator",
                "name": "系统运维管理员",
                "description": "998 系统身份对应的运维权限，不包含日常业务审批权限。",
                "is_system": True,
                "status": "active",
            },
            {
                "code": "organization_manager",
                "name": "组织管理人员",
                "description": "维护成员资料、部门归属和职务关系的业务管理角色。",
                "is_system": True,
                "status": "active",
            },
            {
                "code": "auditor",
                "name": "审计查看员",
                "description": "查看系统审计日志和高风险操作记录。",
                "is_system": True,
                "status": "active",
            },
        ],
    )

    # --- 角色权限关系表 ---
    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("permission_id", sa.BigInteger(), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["permission_id"], ["permissions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("role_id", "permission_id"),
    )

    for permission in CORE_PERMISSIONS:
        insert_role_permission("system_super_admin", permission["code"])
    for permission_code in SYSTEM_OPERATOR_PERMISSIONS:
        insert_role_permission("system_operator", permission_code)
    for permission_code in ORGANIZATION_MANAGER_PERMISSIONS:
        insert_role_permission("organization_manager", permission_code)
    for permission_code in ["system.admin.access", "system.audit.view"]:
        insert_role_permission("auditor", permission_code)

    # --- 用户角色授权表 ---
    op.create_table(
        "user_roles",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("role_id", sa.BigInteger(), nullable=False),
        sa.Column("scope_type", sa.String(length=32), server_default="global", nullable=False),
        sa.Column("scope_id", sa.BigInteger(), nullable=True),
        sa.Column("granted_by", sa.BigInteger(), nullable=True),
        sa.Column(
            "granted_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["granted_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_user_roles_role_id_revoked_at", "user_roles", ["role_id", "revoked_at"])
    op.create_index("ix_user_roles_scope", "user_roles", ["scope_type", "scope_id"])
    op.create_index("ix_user_roles_user_id_revoked_at", "user_roles", ["user_id", "revoked_at"])

    # --- 审计日志表 ---
    op.create_table(
        "audit_logs",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("actor_id", sa.BigInteger(), nullable=True),
        sa.Column("action", sa.String(length=128), nullable=False),
        sa.Column("result", sa.String(length=32), server_default="success", nullable=False),
        sa.Column("risk_level", sa.String(length=32), server_default="medium", nullable=False),
        sa.Column("target_type", sa.String(length=64), nullable=False),
        sa.Column("target_id", sa.String(length=128), nullable=True),
        sa.Column("before_snapshot", sa.JSON(), nullable=True),
        sa.Column("after_snapshot", sa.JSON(), nullable=True),
        sa.Column("extra", sa.JSON(), nullable=True),
        sa.Column("ip_address", sa.String(length=64), nullable=True),
        sa.Column("user_agent", sa.String(length=512), nullable=True),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_audit_logs_action", "audit_logs", ["action"])
    op.create_index("ix_audit_logs_actor_action", "audit_logs", ["actor_id", "action"])
    op.create_index("ix_audit_logs_actor_id", "audit_logs", ["actor_id"])
    op.create_index("ix_audit_logs_created_at", "audit_logs", ["created_at"])
    op.create_index("ix_audit_logs_request_id", "audit_logs", ["request_id"])
    op.create_index("ix_audit_logs_result", "audit_logs", ["result"])
    op.create_index("ix_audit_logs_risk_level", "audit_logs", ["risk_level"])
    op.create_index("ix_audit_logs_target", "audit_logs", ["target_type", "target_id"])
    op.create_index("ix_audit_logs_target_id", "audit_logs", ["target_id"])
    op.create_index("ix_audit_logs_target_type", "audit_logs", ["target_type"])

    # --- 文件元数据表 ---
    op.create_table(
        "files",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("owner_user_id", sa.BigInteger(), nullable=True),
        sa.Column("purpose", sa.String(length=64), nullable=False),
        sa.Column("visibility", sa.String(length=32), server_default="private", nullable=False),
        sa.Column("storage_provider", sa.String(length=32), server_default="minio", nullable=False),
        sa.Column("bucket", sa.String(length=128), nullable=False),
        sa.Column("object_key", sa.String(length=512), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=True),
        sa.Column("content_type", sa.String(length=128), nullable=True),
        sa.Column("size_bytes", sa.BigInteger(), server_default="0", nullable=False),
        sa.Column("sha256", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column(
            "uploaded_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("bucket", "object_key", name="uq_files_bucket_object_key"),
    )
    op.create_index("ix_files_owner_status", "files", ["owner_user_id", "status"])
    op.create_index("ix_files_owner_user_id", "files", ["owner_user_id"])
    op.create_index("ix_files_purpose", "files", ["purpose"])
    op.create_index("ix_files_purpose_status", "files", ["purpose", "status"])
    op.create_index("ix_files_sha256", "files", ["sha256"])
    op.create_index("ix_files_status", "files", ["status"])
    op.create_index("ix_files_visibility", "files", ["visibility"])


def downgrade() -> None:
    """执行回滚迁移。"""

    # 回滚顺序从依赖业务表开始，最后删除权限点和角色定义。
    op.drop_index("ix_files_visibility", table_name="files")
    op.drop_index("ix_files_status", table_name="files")
    op.drop_index("ix_files_sha256", table_name="files")
    op.drop_index("ix_files_purpose_status", table_name="files")
    op.drop_index("ix_files_purpose", table_name="files")
    op.drop_index("ix_files_owner_user_id", table_name="files")
    op.drop_index("ix_files_owner_status", table_name="files")
    op.drop_table("files")

    op.drop_index("ix_audit_logs_target_type", table_name="audit_logs")
    op.drop_index("ix_audit_logs_target_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_target", table_name="audit_logs")
    op.drop_index("ix_audit_logs_risk_level", table_name="audit_logs")
    op.drop_index("ix_audit_logs_result", table_name="audit_logs")
    op.drop_index("ix_audit_logs_request_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_created_at", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_id", table_name="audit_logs")
    op.drop_index("ix_audit_logs_actor_action", table_name="audit_logs")
    op.drop_index("ix_audit_logs_action", table_name="audit_logs")
    op.drop_table("audit_logs")

    op.drop_index("ix_user_roles_user_id_revoked_at", table_name="user_roles")
    op.drop_index("ix_user_roles_scope", table_name="user_roles")
    op.drop_index("ix_user_roles_role_id_revoked_at", table_name="user_roles")
    op.drop_table("user_roles")
    op.drop_table("role_permissions")
    op.drop_index("ix_roles_status", table_name="roles")
    op.drop_table("roles")
    op.drop_index("ix_permissions_status", table_name="permissions")
    op.drop_index("ix_permissions_risk_level", table_name="permissions")
    op.drop_index("ix_permissions_module", table_name="permissions")
    op.drop_table("permissions")
