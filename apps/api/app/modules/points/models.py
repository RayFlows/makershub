# app/modules/points/models.py
"""
积分与账本数据库模型

积分在 MakersHub 中相当于协会内部货币，不能再像旧系统一样放在 users.score 里
被后台资料页直接覆盖。本文件把账户余额、冻结记录和流水事实拆成独立表：

1. point_accounts 保存用户当前总余额和冻结余额缓存；
2. point_holds 保存业务冻结生命周期；
3. point_ledger_entries 保存所有积分变动事实。

余额缓存只允许 points 服务层维护，业务域必须通过服务函数追加流水。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint, func
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
