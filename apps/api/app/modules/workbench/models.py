# app/modules/workbench/models.py
"""
工作台数据库模型

工作台域负责协会日常运营任务。旧系统里的任务只有“待完成/已完成/已取消”，用户一按
完成就直接结束；新版需求明确拆成“执行人提交完成材料”和“发布人审核完成”，并且任务
积分必须引用已维护的积分规则，不能发布时临时改分。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin
from app.modules.points.models import PointLedgerEntry, PointRule


class WorkbenchTask(Base, IdMixin, TimestampMixin):
    """
    工作台任务。

    指定任务发布后直接待完成；悬赏任务先待领取，领取后进入待完成。任务完成必须由
    执行人提交材料，再由发布人审核；审核通过后才调用积分域按规则发放积分。
    """

    __tablename__ = "workbench_tasks"

    # --- 任务基础信息 ---
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    assignment_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    # --- 任务参与人 ---
    publisher_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    assignee_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # --- 积分规则 ---
    point_rule_id: Mapped[int] = mapped_column(
        ForeignKey("point_rules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # --- 完成提交与审核 ---
    submission_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    submitted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    reviewed_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    review_comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    point_ledger_entry_id: Mapped[int | None] = mapped_column(
        ForeignKey("point_ledger_entries.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    point_rule: Mapped[PointRule] = relationship()
    point_ledger_entry: Mapped[PointLedgerEntry | None] = relationship()

    __table_args__ = (
        Index("ix_workbench_tasks_status_created", "status", "created_at"),
        Index("ix_workbench_tasks_assignee_status", "assignee_id", "status"),
        Index("ix_workbench_tasks_publisher_status", "publisher_id", "status"),
        Index("ix_workbench_tasks_visibility_status", "visibility", "status"),
    )
