# app/modules/resources/models.py
"""
资源域数据库模型

旧后端把物资表 `stuffs` 同时当作资源资料和库存表使用，借用审批时直接扣
`number_remain`。新版仍保留“审批通过才扣库存、归还才恢复库存”的业务语义，
但把资源台账独立在 resources 域内，借用域只能通过明确服务方法修改库存。
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin


class ResourceCategory(Base, IdMixin, TimestampMixin):
    """
    资源分类。

    分类先服务物资，后续场地和工位也复用同一张表。`resource_type` 决定分类归属，
    避免前端或管理端把不同类型资源混在同一个下拉列表里。
    """

    __tablename__ = "resource_categories"

    # --- 分类主体 ---
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    materials: Mapped[list[Material]] = relationship(back_populates="category")

    __table_args__ = (
        Index("ix_resource_categories_type_status", "resource_type", "status"),
    )


class Material(Base, IdMixin, TimestampMixin):
    """
    物资台账。

    `total_quantity` 表示账面总量，`available_quantity` 表示当前可借数量。借用审批
    成功后减少可借数量，归还后恢复可借数量；所有跨业务修改都必须留在服务层。
    """

    __tablename__ = "materials"

    # --- 物资基础信息 ---
    category_id: Mapped[int | None] = mapped_column(
        ForeignKey("resource_categories.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    cabinet_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    shelf_no: Mapped[str | None] = mapped_column(String(80), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="available", index=True)

    # --- 库存与押金 ---
    total_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    available_quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    deposit_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    # --- 操作线索 ---
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    updated_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    category: Mapped[ResourceCategory | None] = relationship(back_populates="materials")

    __table_args__ = (
        Index("ix_materials_category_status", "category_id", "status"),
        Index("ix_materials_status_available", "status", "available_quantity"),
    )
