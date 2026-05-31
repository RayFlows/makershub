# app/modules/borrowing/models.py
"""
借用域数据库模型

旧物资借用以 `stuff_borrows`、`borrow_items` 和物资库存字段共同表达状态。新版把
申请主表、明细、审核记录和归还记录拆开，保留业务事实，避免取消或驳回后直接删除
记录导致后续无法追踪。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin
from app.modules.points.models import PointHold
from app.modules.resources.models import Material


class BorrowApplication(Base, IdMixin, TimestampMixin):
    """
    借用申请。

    第一阶段只开放物资借用，场地和工位沿用同一生命周期后续再补明细字段。审批通过时
    扣减可借库存并冻结押金；归还时恢复库存并根据归还情况解冻或扣除押金。
    """

    __tablename__ = "borrow_applications"

    # --- 申请主体 ---
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    applicant_name_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    applicant_student_id_snapshot: Mapped[str] = mapped_column(String(32), nullable=False)
    applicant_phone_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    applicant_email_snapshot: Mapped[str] = mapped_column(String(255), nullable=False)
    applicant_grade_snapshot: Mapped[str] = mapped_column(String(20), nullable=False)
    applicant_major_snapshot: Mapped[str] = mapped_column(String(100), nullable=False)
    borrow_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    usage_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    project_id: Mapped[int | None] = mapped_column(nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    expected_return_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # --- 押金与取消 ---
    deposit_points: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    point_hold_id: Mapped[int | None] = mapped_column(
        ForeignKey("point_holds.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    point_hold: Mapped[PointHold | None] = relationship()
    items: Mapped[list[BorrowItem]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    reviews: Mapped[list[BorrowReview]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )
    returns: Mapped[list[BorrowReturn]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_borrow_applications_applicant_status", "applicant_id", "status"),
        Index("ix_borrow_applications_type_status", "borrow_type", "status"),
        Index("ix_borrow_applications_status_created", "status", "created_at"),
    )


class BorrowItem(Base, IdMixin, TimestampMixin):
    """借用申请明细。"""

    __tablename__ = "borrow_items"

    application_id: Mapped[int] = mapped_column(
        ForeignKey("borrow_applications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    material_id: Mapped[int | None] = mapped_column(
        ForeignKey("materials.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    material_name_snapshot: Mapped[str] = mapped_column(String(120), nullable=False)
    category_name_snapshot: Mapped[str | None] = mapped_column(String(120), nullable=True)
    unit_deposit_points_snapshot: Mapped[int] = mapped_column(Integer, nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)

    application: Mapped[BorrowApplication] = relationship(back_populates="items")
    material: Mapped[Material | None] = relationship()

    __table_args__ = (
        Index("ix_borrow_items_application_resource", "application_id", "resource_type"),
    )


class BorrowReview(Base, IdMixin, TimestampMixin):
    """借用审核记录。"""

    __tablename__ = "borrow_reviews"

    application_id: Mapped[int] = mapped_column(
        ForeignKey("borrow_applications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    reviewer_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    application: Mapped[BorrowApplication] = relationship(back_populates="reviews")

    __table_args__ = (
        Index("ix_borrow_reviews_application_reviewed", "application_id", "reviewed_at"),
    )


class BorrowReturn(Base, IdMixin, TimestampMixin):
    """借用归还记录。"""

    __tablename__ = "borrow_returns"

    application_id: Mapped[int] = mapped_column(
        ForeignKey("borrow_applications.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    operator_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    returned_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    condition: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    point_action: Mapped[str | None] = mapped_column(String(32), nullable=True)

    application: Mapped[BorrowApplication] = relationship(back_populates="returns")

    __table_args__ = (
        Index("ix_borrow_returns_application_returned", "application_id", "returned_at"),
    )
