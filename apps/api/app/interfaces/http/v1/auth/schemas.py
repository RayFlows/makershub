# app/interfaces/http/v1/auth/schemas.py
"""
身份认证接口请求与响应模型

接口层 schema 只描述 HTTP 契约，不承载业务规则。身份业务规则已经拆到
modules/identity 下的 accounts、sessions、email_codes 和 bootstrap 等能力模块。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WechatLoginRequest(BaseModel):
    """小程序微信登录请求。"""

    code: str | None = Field(default=None, description="wx.login 返回的临时 code")
    dev_openid: str | None = Field(
        default=None,
        description="本地开发和测试使用的模拟 openid，生产环境禁止使用",
    )
    display_name: str | None = Field(default=None, max_length=80, description="可选显示名")


class UserSummary(BaseModel):
    """当前用户摘要。"""

    id: int
    display_name: str
    avatar_url: str | None
    status: str
    email: str | None = None


class TokenResponse(BaseModel):
    """登录成功后的令牌响应。"""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    expires_at: datetime
    refresh_expires_at: datetime
    user: UserSummary


class RefreshTokenRequest(BaseModel):
    """刷新访问令牌请求。"""

    refresh_token: str = Field(min_length=1, description="登录或上次刷新返回的 refresh token")


class LogoutRequest(BaseModel):
    """退出登录请求。"""

    refresh_token: str = Field(min_length=1, description="需要撤销的 refresh token")


class SendEmailCodeRequest(BaseModel):
    """发送邮箱验证码请求。"""

    email: str = Field(min_length=3, max_length=255, description="目标邮箱")
    purpose: str = Field(default="bind_email", description="验证码用途")


class SendEmailCodeResponse(BaseModel):
    """发送邮箱验证码响应。"""

    email: str
    purpose: str
    expires_at: datetime
    delivery_mode: str
    dev_code: str | None = None


class BindEmailRequest(BaseModel):
    """绑定邮箱请求。"""

    email: str = Field(min_length=3, max_length=255, description="已接收验证码的邮箱")
    code: str = Field(min_length=6, max_length=6, description="6 位邮箱验证码")


class BindEmailResponse(BaseModel):
    """绑定邮箱响应。"""

    email: str
    created: bool
    password_required: bool
    user: UserSummary


class EmailFirstLoginRequest(BaseModel):
    """网页端首次邮箱验证码登录请求。"""

    email: str = Field(min_length=3, max_length=255, description="已绑定但尚未设置密码的邮箱")
    code: str = Field(min_length=6, max_length=6, description="6 位邮箱验证码")


class EmailFirstLoginResponse(TokenResponse):
    """网页端首次邮箱验证码登录响应。"""

    password_required: bool = True


class SetPasswordRequest(BaseModel):
    """首次设置密码请求。"""

    password: str = Field(min_length=8, max_length=128, description="新的登录密码")


class SetPasswordResponse(BaseModel):
    """首次设置密码响应。"""

    password_set: bool
    user: UserSummary


class PasswordLoginRequest(BaseModel):
    """邮箱密码登录请求。"""

    email: str = Field(min_length=3, max_length=255, description="已绑定邮箱")
    password: str = Field(min_length=1, max_length=128, description="登录密码")
