# app/modules/points/models.py
"""
积分与账本数据库模型

积分在 MakersHub 中相当于协会内部货币，不能再像旧系统一样放在 users.score 里
被后台资料页直接覆盖。本文件把账户余额、冻结记录和流水事实拆成独立表：

1. point_accounts 保存用户当前总余额和冻结余额缓存；
2. point_holds 保存业务冻结生命周期；
3. point_ledger_entries 保存所有积分变动事实；
4. point_rules 保存固定规则和审批生成的一次性任务模板；
5. temporary_point_rules 保存临时积分规则申请、审批和撤回状态。

余额缓存只允许 points 服务层维护，业务域必须通过服务函数追加流水。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin
from app.shared.time import utc_now

point_amount_type = BigInteger().with_variant(Integer, "sqlite")


class PointAccount(Base, IdMixin, TimestampMixin):
    """
    用户积分账户。

    balance 表示账户总积分，包含已冻结部分；frozen_balance 表示当前被冻结、暂不可用
    的积分。可用余额由 `balance - frozen_balance` 得到，不单独落库，避免多字段漂移。
    """

    __tablename__ = "point_accounts"

    # --- 账户归属 ---
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
        index=True,
    )

    # --- 余额缓存 ---
    balance: Mapped[int] = mapped_column(point_amount_type, nullable=False, default=0)
    frozen_balance: Mapped[int] = mapped_column(point_amount_type, nullable=False, default=0)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    ledger_entries: Mapped[list[PointLedgerEntry]] = relationship(back_populates="account")
    holds: Mapped[list[PointHold]] = relationship(back_populates="account")

    @property
    def available_balance(self) -> int:
        """当前可用余额。"""

        return self.balance - self.frozen_balance


class PointHold(Base, IdMixin, TimestampMixin):
    """
    积分冻结记录。

    借用押金、3D 打印接单后的预扣等场景先冻结积分；后续可以解冻，也可以把冻结
    积分转为扣除。冻结记录保留业务来源，便于业务域和账本域对账。
    """

    __tablename__ = "point_holds"

    # --- 账户与用户 ---
    account_id: Mapped[int] = mapped_column(
        ForeignKey("point_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # --- 冻结主体 ---
    amount: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- 操作线索 ---
    created_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    released_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    deducted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    account: Mapped[PointAccount] = relationship(back_populates="holds")

    __table_args__ = (
        Index("ix_point_holds_user_status", "user_id", "status"),
        Index("ix_point_holds_business", "business_type", "business_id"),
    )


class PointLedgerEntry(Base, IdMixin):
    """
    积分流水。

    流水是积分事实来源，原则上不删除、不原地修改。撤销、追回和异常修正必须追加
    新流水表达反向变化，而不是覆盖旧记录。
    """

    __tablename__ = "point_ledger_entries"

    # --- 账户与用户 ---
    account_id: Mapped[int] = mapped_column(
        ForeignKey("point_accounts.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    # --- 流水主体 ---
    direction: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    amount: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    balance_after: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    available_balance_after: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    frozen_balance_after: Mapped[int] = mapped_column(point_amount_type, nullable=False)

    # --- 业务来源与幂等 ---
    business_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    business_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    related_hold_id: Mapped[int | None] = mapped_column(
        ForeignKey("point_holds.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # --- 操作线索 ---
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        default=lambda: utc_now(),
    )

    account: Mapped[PointAccount] = relationship(back_populates="ledger_entries")

    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_point_ledger_entries_idempotency_key"),
        Index("ix_point_ledger_entries_user_created", "user_id", "created_at"),
        Index("ix_point_ledger_entries_business", "business_type", "business_id"),
    )


class PointRule(Base, IdMixin, TimestampMixin):
    """
    积分规则表。

    固定规则用于日常任务、值班、打扫卫生等可自动化积分发放；临时规则审批通过后
    会生成一条 `temporary_task_template` 类型的规则，后续任务域只能引用这条模板，
    不能在发布任务时临时修改积分。
    """

    __tablename__ = "point_rules"

    # --- 稳定规则标识 ---
    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    # --- 发放策略 ---
    amount: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    effective_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    effective_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

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

    __table_args__ = (
        Index("ix_point_rules_type_status", "rule_type", "status"),
        Index("ix_point_rules_effective_window", "effective_from", "effective_to"),
    )


class TemporaryPointRule(Base, IdMixin, TimestampMixin):
    """
    临时积分规则申请表。

    特殊非模板任务不能直接发布，必须先提交临时规则申请。审批通过后系统生成一次性
    任务模板；撤回只停止后续使用，不默认追回已发积分。确需追回时走反向流水修正。
    """

    __tablename__ = "temporary_point_rules"

    # --- 申请内容 ---
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    task_type: Mapped[str] = mapped_column(String(64), nullable=False)
    target_scope: Mapped[str] = mapped_column(String(64), nullable=False, default="members")
    department_id: Mapped[int | None] = mapped_column(
        ForeignKey("departments.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    completion_requirements: Mapped[str | None] = mapped_column(Text, nullable=True)
    amount_per_completion: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    max_participants: Mapped[int] = mapped_column(Integer, nullable=False)
    total_points_limit: Mapped[int] = mapped_column(point_amount_type, nullable=False)
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    effective_to: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    # --- 审批状态 ---
    approval_status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)
    applicant_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    approved_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    approval_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    rejected_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- 发布与撤回 ---
    generated_point_rule_id: Mapped[int | None] = mapped_column(
        ForeignKey("point_rules.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    revoke_status: Mapped[str] = mapped_column(String(32), nullable=False, default="none", index=True)
    revoked_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoke_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    revoke_impact_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    generated_point_rule: Mapped[PointRule | None] = relationship()

    __table_args__ = (
        Index("ix_temporary_point_rules_status", "approval_status", "revoke_status"),
        Index("ix_temporary_point_rules_applicant_status", "applicant_id", "approval_status"),
        Index("ix_temporary_point_rules_effective_window", "effective_from", "effective_to"),
    )


class TemporaryPointRuleEvent(Base, IdMixin):
    """
    临时积分规则事件日志。

    审计日志记录“谁通过哪个入口做了操作”，本表记录临时规则自己的生命周期状态变更。
    两者不能互相替代：审计用于追责，领域事件用于后续任务、通知和对账。
    """

    __tablename__ = "temporary_point_rule_events"

    # --- 事件主体 ---
    temporary_rule_id: Mapped[int] = mapped_column(
        ForeignKey("temporary_point_rules.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    event_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )

    # --- 事件内容 ---
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    extra: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
        default=lambda: utc_now(),
    )

    __table_args__ = (
        Index("ix_temporary_point_rule_events_rule_created", "temporary_rule_id", "created_at"),
    )
