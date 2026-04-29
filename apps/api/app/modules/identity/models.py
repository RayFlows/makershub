# app/modules/identity/models.py
"""
身份域数据库模型

这里刻意把“用户主体”和“登录凭证”分开：
users 表示系统里的一个人，local_accounts 和 wechat_accounts 只是登录方式。
这能避免把用户直接等同于 openid、unionid 或邮箱。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database.base import Base, IdMixin, SoftDeleteMixin, TimestampMixin


class User(Base, IdMixin, TimestampMixin, SoftDeleteMixin):
    """系统内部用户主体。

    一个用户可以先由小程序微信登录创建，后续再绑定邮箱和密码。
    第一个 999 则允许通过运维初始化命令先创建本地账号。
    """

    __tablename__ = "users"

    # --- 基础资料 ---
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    avatar_url: Mapped[str | None] = mapped_column(String(512), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    remark: Mapped[str | None] = mapped_column(Text, nullable=True)

    # --- 登录凭证关系 ---
    # 当前第一版约束为一个用户最多一个本地账号、一个微信账号。
    # 如果后续支持多个邮箱或多个微信身份，需要先调整需求和唯一约束。
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
    """邮箱密码登录凭证。

    password_hash 允许为空，用于表达“邮箱已绑定，但网页端首次登录尚未设置密码”。
    为空时不能进行密码登录，只能走邮箱验证码首次登录和强制设置密码流程。
    """

    __tablename__ = "local_accounts"

    # --- 账号归属 ---
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    # --- 邮箱与密码状态 ---
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    password_set_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    user: Mapped[User] = relationship(back_populates="local_account")

    __table_args__ = (Index("ix_local_accounts_email_status", "email", "status"),)


class WechatAccount(Base, IdMixin, TimestampMixin):
    """微信登录凭证。

    第一版小程序用户以 openid 作为稳定登录入口；unionid 可能暂时拿不到，
    所以它是可空字段，但一旦出现就必须保持唯一且不能和已有账号冲突。
    """

    __tablename__ = "wechat_accounts"

    # --- 账号归属 ---
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        unique=True,
    )
    # --- 微信身份字段 ---
    openid: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    unionid: Mapped[str | None] = mapped_column(String(128), nullable=True, unique=True)
    session_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    bound_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)

    user: Mapped[User] = relationship(back_populates="wechat_account")

    __table_args__ = (Index("ix_wechat_accounts_openid_status", "openid", "status"),)


class EmailVerificationCode(Base, IdMixin, TimestampMixin):
    """邮箱验证码记录。

    同一张表承载绑定邮箱、首次登录、重置密码和更换邮箱等场景，
    具体行为由 purpose 区分，后续服务层负责校验发送频率和消费幂等。
    """

    __tablename__ = "email_verification_codes"

    # --- 验证码主体 ---
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
