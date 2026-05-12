# app/modules/identity/accounts/__init__.py
"""
身份账号能力导出

这里聚合微信身份和邮箱密码账号服务。上层应该直接依赖本能力包，避免再回到
单个庞大 service 文件的旧结构。
"""

from app.modules.identity.accounts.email_password import (
    bind_email_with_code,
    bind_verified_email_to_user,
    complete_first_login_with_code,
    load_active_user_for_email_password_account,
    login_email_password_account_with_password,
    set_email_password_account_password,
)
from app.modules.identity.accounts.wechat import EXTERNAL_MEMBER_POSITION_CODE, login_wechat_identity

__all__ = [
    "EXTERNAL_MEMBER_POSITION_CODE",
    "bind_email_with_code",
    "bind_verified_email_to_user",
    "complete_first_login_with_code",
    "load_active_user_for_email_password_account",
    "login_email_password_account_with_password",
    "login_wechat_identity",
    "set_email_password_account_password",
]
