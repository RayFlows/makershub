# app/modules/identity/__init__.py
"""
身份与登录模块导出

identity 负责用户主体、微信身份、邮箱密码账号、邮箱验证码等登录相关模型。
部门、职务和权限授予属于 organization/permission 等模块，不在这里直接处理。
"""

from app.modules.identity.models import (
    AuthSession,
    EmailPasswordAccount,
    EmailVerificationCode,
    User,
    WechatAccount,
)

__all__ = ["AuthSession", "EmailVerificationCode", "EmailPasswordAccount", "User", "WechatAccount"]
