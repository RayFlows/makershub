# app/modules/identity/repositories/__init__.py
"""
身份域仓储聚合

IdentityRepository 由多个能力仓储 mixin 组合而成。外部模块可以依赖本包暴露的
IdentityRepository，但不应该直接依赖内部 mixin，避免把身份域的查询拆分细节泄露出去。
"""

from __future__ import annotations

from app.modules.identity.repositories.accounts import (
    EmailPasswordAccountRepositoryMixin,
    WechatAccountRepositoryMixin,
)
from app.modules.identity.repositories.base import IdentityRepositoryBase
from app.modules.identity.repositories.email_codes import EmailVerificationCodeRepositoryMixin
from app.modules.identity.repositories.sessions import AuthSessionRepositoryMixin


class IdentityRepository(
    IdentityRepositoryBase,
    EmailPasswordAccountRepositoryMixin,
    WechatAccountRepositoryMixin,
    EmailVerificationCodeRepositoryMixin,
    AuthSessionRepositoryMixin,
):
    """身份域统一仓储门面。"""


__all__ = ["IdentityRepository"]
