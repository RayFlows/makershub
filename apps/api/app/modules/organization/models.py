from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, TimestampMixin


class Position(Base, IdMixin, TimestampMixin):
    __tablename__ = "positions"

    code: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    sort_order: Mapped[int] = mapped_column(default=0, nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    user_positions: Mapped[list[UserPosition]] = relationship(back_populates="position")


class UserPosition(Base, IdMixin, TimestampMixin):
    __tablename__ = "user_positions"

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    position_id: Mapped[int] = mapped_column(
        ForeignKey("positions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    department_id: Mapped[int | None] = mapped_column(nullable=True)
    scope_type: Mapped[str] = mapped_column(String(32), nullable=False, default="global")
    scope_id: Mapped[int | None] = mapped_column(nullable=True)
    granted_by: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    position: Mapped[Position] = relationship(back_populates="user_positions")

    __table_args__ = (
        Index("ix_user_positions_user_id_revoked_at", "user_id", "revoked_at"),
        Index("ix_user_positions_position_id_revoked_at", "position_id", "revoked_at"),
    )
