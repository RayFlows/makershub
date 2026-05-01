# app/modules/audit/models.py
"""
审计日志数据库模型

运行日志可以轮转和压缩，审计日志则是业务追责和异常恢复的事实线索。
本表默认只追加：谁、何时、对什么对象、执行什么动作、结果如何，以及必要的
前后快照和请求上下文。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import JSON, DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, IdMixin


class AuditLog(Base, IdMixin):
    """
    审计日志表。

    审计记录不使用 updated_at，不提供通用更新入口。确实需要修正时，应该追加一条
    新的补充审计记录，而不是原地修改旧记录。
    """

    __tablename__ = "audit_logs"

    # --- 操作人与动作 ---
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(32), nullable=False, default="success", index=True)
    risk_level: Mapped[str] = mapped_column(String(32), nullable=False, default="medium", index=True)

    # --- 目标对象 ---
    target_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    # --- 数据快照 ---
    before_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    extra: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)

    # --- 请求上下文 ---
    ip_address: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(512), nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )

    __table_args__ = (
        Index("ix_audit_logs_target", "target_type", "target_id"),
        Index("ix_audit_logs_actor_action", "actor_id", "action"),
    )

