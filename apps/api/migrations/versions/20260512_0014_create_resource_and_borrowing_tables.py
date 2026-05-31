# migrations/versions/20260512_0014_create_resource_and_borrowing_tables.py
"""
创建资源台账和物资借用表

Revision ID: 20260512_0014
Revises: 20260512_0013
Create Date: 2026-05-12

需求背景:
旧后端的物资借用把申请状态、库存扣减和归还恢复分散在多个接口里，容易出现“申请已
归还但库存未恢复”或“库存已扣但押金没有记录”的问题。新版把资源台账、借用生命周期
和积分押金分别建模，通过服务层在同一事务里编排。
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "20260512_0014"
down_revision = "20260512_0013"
branch_labels = None
depends_on = None


RESOURCE_BORROWING_PERMISSIONS = [
    {
        "code": "resources.material.manage",
        "name": "维护物资台账",
        "module": "resources",
        "description": "维护物资分类、物资资料和库存快照。",
        "risk_level": "high",
    },
    {
        "code": "borrowing.application.review",
        "name": "审核借用申请",
        "module": "borrowing",
        "description": "审核物资借用申请，确认归还，并触发库存和押金状态变化。",
        "risk_level": "high",
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
    """幂等插入资源和借用权限点。"""

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

    # --- 资源分类 ---
    op.create_table(
        "resource_categories",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), server_default="active", nullable=False),
        sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
        *timestamp_columns(),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_resource_categories_resource_type", "resource_categories", ["resource_type"])
    op.create_index("ix_resource_categories_status", "resource_categories", ["status"])
    op.create_index(
        "ix_resource_categories_type_status",
        "resource_categories",
        ["resource_type", "status"],
    )

    # --- 物资台账 ---
    op.create_table(
        "materials",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("category_id", sa.BigInteger(), nullable=True),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(length=120), nullable=True),
        sa.Column("cabinet_no", sa.String(length=80), nullable=True),
        sa.Column("shelf_no", sa.String(length=80), nullable=True),
        sa.Column("status", sa.String(length=32), server_default="available", nullable=False),
        sa.Column("total_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("available_quantity", sa.Integer(), server_default="0", nullable=False),
        sa.Column("deposit_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_by", sa.BigInteger(), nullable=True),
        sa.Column("updated_by", sa.BigInteger(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("total_quantity >= 0", name="ck_materials_total_quantity_non_negative"),
        sa.CheckConstraint("available_quantity >= 0", name="ck_materials_available_quantity_non_negative"),
        sa.CheckConstraint(
            "available_quantity <= total_quantity",
            name="ck_materials_available_not_greater_than_total",
        ),
        sa.CheckConstraint("deposit_points >= 0", name="ck_materials_deposit_points_non_negative"),
        sa.ForeignKeyConstraint(["category_id"], ["resource_categories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_materials_category_id", "materials", ["category_id"])
    op.create_index("ix_materials_name", "materials", ["name"])
    op.create_index("ix_materials_status", "materials", ["status"])
    op.create_index("ix_materials_created_by", "materials", ["created_by"])
    op.create_index("ix_materials_updated_by", "materials", ["updated_by"])
    op.create_index("ix_materials_category_status", "materials", ["category_id", "status"])
    op.create_index("ix_materials_status_available", "materials", ["status", "available_quantity"])

    # --- 借用申请主表 ---
    op.create_table(
        "borrow_applications",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("applicant_id", sa.BigInteger(), nullable=False),
        sa.Column("applicant_name_snapshot", sa.String(length=100), nullable=False),
        sa.Column("applicant_student_id_snapshot", sa.String(length=32), nullable=False),
        sa.Column("applicant_phone_snapshot", sa.String(length=20), nullable=False),
        sa.Column("applicant_email_snapshot", sa.String(length=255), nullable=False),
        sa.Column("applicant_grade_snapshot", sa.String(length=20), nullable=False),
        sa.Column("applicant_major_snapshot", sa.String(length=100), nullable=False),
        sa.Column("borrow_type", sa.String(length=32), nullable=False),
        sa.Column("usage_type", sa.String(length=32), nullable=False),
        sa.Column("project_id", sa.BigInteger(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("expected_return_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("deposit_points", sa.Integer(), server_default="0", nullable=False),
        sa.Column("point_hold_id", sa.BigInteger(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
        *timestamp_columns(),
        sa.CheckConstraint("deposit_points >= 0", name="ck_borrow_applications_deposit_non_negative"),
        sa.ForeignKeyConstraint(["applicant_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["point_hold_id"], ["point_holds.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_borrow_applications_applicant_id", "borrow_applications", ["applicant_id"])
    op.create_index("ix_borrow_applications_borrow_type", "borrow_applications", ["borrow_type"])
    op.create_index("ix_borrow_applications_usage_type", "borrow_applications", ["usage_type"])
    op.create_index("ix_borrow_applications_project_id", "borrow_applications", ["project_id"])
    op.create_index("ix_borrow_applications_status", "borrow_applications", ["status"])
    op.create_index("ix_borrow_applications_point_hold_id", "borrow_applications", ["point_hold_id"])
    op.create_index(
        "ix_borrow_applications_applicant_status",
        "borrow_applications",
        ["applicant_id", "status"],
    )
    op.create_index(
        "ix_borrow_applications_type_status",
        "borrow_applications",
        ["borrow_type", "status"],
    )
    op.create_index(
        "ix_borrow_applications_status_created",
        "borrow_applications",
        ["status", "created_at"],
    )

    # --- 借用明细、审核和归还记录 ---
    op.create_table(
        "borrow_items",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("resource_type", sa.String(length=32), nullable=False),
        sa.Column("material_id", sa.BigInteger(), nullable=True),
        sa.Column("material_name_snapshot", sa.String(length=120), nullable=False),
        sa.Column("category_name_snapshot", sa.String(length=120), nullable=True),
        sa.Column("unit_deposit_points_snapshot", sa.Integer(), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        *timestamp_columns(),
        sa.CheckConstraint("quantity > 0", name="ck_borrow_items_quantity_positive"),
        sa.CheckConstraint(
            "unit_deposit_points_snapshot >= 0",
            name="ck_borrow_items_unit_deposit_non_negative",
        ),
        sa.ForeignKeyConstraint(["application_id"], ["borrow_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["material_id"], ["materials.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_borrow_items_application_id", "borrow_items", ["application_id"])
    op.create_index("ix_borrow_items_resource_type", "borrow_items", ["resource_type"])
    op.create_index("ix_borrow_items_material_id", "borrow_items", ["material_id"])
    op.create_index(
        "ix_borrow_items_application_resource",
        "borrow_items",
        ["application_id", "resource_type"],
    )

    op.create_table(
        "borrow_reviews",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("reviewer_id", sa.BigInteger(), nullable=False),
        sa.Column("decision", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["application_id"], ["borrow_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewer_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_borrow_reviews_application_id", "borrow_reviews", ["application_id"])
    op.create_index("ix_borrow_reviews_reviewer_id", "borrow_reviews", ["reviewer_id"])
    op.create_index("ix_borrow_reviews_decision", "borrow_reviews", ["decision"])
    op.create_index(
        "ix_borrow_reviews_application_reviewed",
        "borrow_reviews",
        ["application_id", "reviewed_at"],
    )

    op.create_table(
        "borrow_returns",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("application_id", sa.BigInteger(), nullable=False),
        sa.Column("operator_id", sa.BigInteger(), nullable=False),
        sa.Column("returned_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("condition", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("point_action", sa.String(length=32), nullable=True),
        *timestamp_columns(),
        sa.ForeignKeyConstraint(["application_id"], ["borrow_applications.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["operator_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_borrow_returns_application_id", "borrow_returns", ["application_id"])
    op.create_index("ix_borrow_returns_operator_id", "borrow_returns", ["operator_id"])
    op.create_index("ix_borrow_returns_condition", "borrow_returns", ["condition"])
    op.create_index(
        "ix_borrow_returns_application_returned",
        "borrow_returns",
        ["application_id", "returned_at"],
    )

    # --- 权限点和预置角色 ---
    for permission in RESOURCE_BORROWING_PERMISSIONS:
        insert_permission(permission)
    insert_role(
        code="resource_manager",
        name="资源与借用管理员",
        description="维护物资台账，审核物资借用申请，并确认归还。",
    )
    insert_role_permission("resource_manager", "system.admin.access")
    insert_role_permission("resource_manager", "resources.material.manage")
    insert_role_permission("resource_manager", "borrowing.application.review")


def downgrade() -> None:
    """执行回滚迁移。"""

    op.execute(
        sa.text(
            """
            DELETE FROM role_permissions
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'resource_manager'
            )
               OR permission_id IN (
                SELECT id FROM permissions
                WHERE code IN ('resources.material.manage', 'borrowing.application.review')
            )
            """,
        ),
    )
    op.execute(
        sa.text(
            """
            DELETE FROM user_role_grants
            WHERE role_id IN (
                SELECT id FROM roles WHERE code = 'resource_manager'
            )
            """,
        ),
    )
    op.execute(sa.text("DELETE FROM roles WHERE code = 'resource_manager'"))
    op.execute(
        sa.text(
            """
            DELETE FROM permissions
            WHERE code IN ('resources.material.manage', 'borrowing.application.review')
            """,
        ),
    )

    op.drop_index("ix_borrow_returns_application_returned", table_name="borrow_returns")
    op.drop_index("ix_borrow_returns_condition", table_name="borrow_returns")
    op.drop_index("ix_borrow_returns_operator_id", table_name="borrow_returns")
    op.drop_index("ix_borrow_returns_application_id", table_name="borrow_returns")
    op.drop_table("borrow_returns")

    op.drop_index("ix_borrow_reviews_application_reviewed", table_name="borrow_reviews")
    op.drop_index("ix_borrow_reviews_decision", table_name="borrow_reviews")
    op.drop_index("ix_borrow_reviews_reviewer_id", table_name="borrow_reviews")
    op.drop_index("ix_borrow_reviews_application_id", table_name="borrow_reviews")
    op.drop_table("borrow_reviews")

    op.drop_index("ix_borrow_items_application_resource", table_name="borrow_items")
    op.drop_index("ix_borrow_items_material_id", table_name="borrow_items")
    op.drop_index("ix_borrow_items_resource_type", table_name="borrow_items")
    op.drop_index("ix_borrow_items_application_id", table_name="borrow_items")
    op.drop_table("borrow_items")

    op.drop_index("ix_borrow_applications_status_created", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_type_status", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_applicant_status", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_point_hold_id", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_status", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_project_id", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_usage_type", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_borrow_type", table_name="borrow_applications")
    op.drop_index("ix_borrow_applications_applicant_id", table_name="borrow_applications")
    op.drop_table("borrow_applications")

    op.drop_index("ix_materials_status_available", table_name="materials")
    op.drop_index("ix_materials_category_status", table_name="materials")
    op.drop_index("ix_materials_updated_by", table_name="materials")
    op.drop_index("ix_materials_created_by", table_name="materials")
    op.drop_index("ix_materials_status", table_name="materials")
    op.drop_index("ix_materials_name", table_name="materials")
    op.drop_index("ix_materials_category_id", table_name="materials")
    op.drop_table("materials")

    op.drop_index("ix_resource_categories_type_status", table_name="resource_categories")
    op.drop_index("ix_resource_categories_status", table_name="resource_categories")
    op.drop_index("ix_resource_categories_resource_type", table_name="resource_categories")
    op.drop_table("resource_categories")
