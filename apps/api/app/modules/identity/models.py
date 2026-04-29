from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class User(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    __tablename__ = "users"

    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    local_account: Mapped[LocalAccount | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )
    wechat_account: Mapped[WechatAccount | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        uselist=False,
    )


class LocalAccount(Base, IdMixin, TimestampMixin):
    __tablename__ = "local_accounts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    password_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    user: Mapped[User] = relationship(back_populates="local_account")

    __table_args__ = (Index("ix_local_accounts_email_status", "email", "status"),)


class WechatAccount(Base, IdMixin, TimestampMixin):
    __tablename__ = "wechat_accounts"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    openid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    unionid: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    session_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    user: Mapped[User] = relationship(back_populates="wechat_account")

    __table_args__ = (Index("ix_wechat_accounts_openid_status", "openid", "status"),)


class EmailVerificationCode(Base, IdMixin, TimestampMixin):
    __tablename__ = "email_verification_codes"

    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    purpose: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    consumed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    request_ip: Mapped[str | None] = mapped_column(String(64), nullable=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
    )

    __table_args__ = (
        Index("ix_email_verification_codes_email_purpose", "email", "purpose"),
        Index("ix_email_verification_codes_user_id", "user_id"),
    )
