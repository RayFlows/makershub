# app/modules/identity/types.py
"""
身份域服务返回结构

本文件只放身份域服务层对外返回的数据结构，避免各能力模块互相导入具体实现。
用户主体、微信身份、邮箱密码账号和登录会话仍以 ORM 模型作为业务事实来源。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from app.core.security import AccessToken
from app.modules.identity.models import AuthSession, EmailPasswordAccount, User, WechatAccount
from app.modules.organization.models import UserPosition


@dataclass(frozen=True)
class BootstrapSuperAdminResult:
    """初始化 999 的返回结果。"""

    user: User
    email_password_account: EmailPasswordAccount
    user_position: UserPosition
    created: bool


@dataclass(frozen=True)
class WechatLoginResult:
    """微信登录的返回结果。"""

    user: User
    wechat_account: WechatAccount
    created: bool


@dataclass(frozen=True)
class BindEmailResult:
    """邮箱绑定的返回结果。"""

    user: User
    email_password_account: EmailPasswordAccount
    created: bool


@dataclass(frozen=True)
class EmailPasswordAccountAuthResult:
    """邮箱密码账号登录或首次登录校验结果。"""

    user: User
    email_password_account: EmailPasswordAccount
    password_required: bool


@dataclass(frozen=True)
class PasswordSetResult:
    """设置密码结果。"""

    user: User
    email_password_account: EmailPasswordAccount
    password_set: bool


@dataclass(frozen=True)
class AuthTokenPair:
    """登录令牌对。"""

    user: User
    auth_session: AuthSession
    access_token: AccessToken
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True)
class EmailVerificationIssueResult:
    """邮箱验证码签发结果。"""

    email: str
    purpose: str
    expires_at: datetime
    delivery_mode: str
    dev_code: str | None
