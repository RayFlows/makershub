# app/interfaces/http/v1/auth/schemas.py
"""
身份认证接口请求与响应模型

接口层 schema 只描述 HTTP 契约，不承载业务规则。
业务规则仍由 modules/identity/service.py 负责。
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
