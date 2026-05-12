# app/modules/identity/email_codes/__init__.py
"""
邮箱验证码能力导出
"""

from app.modules.identity.email_codes.service import (
    consume_email_verification_code,
    generate_email_verification_code,
    hash_email_verification_code,
    issue_email_verification_code,
    normalize_email_code_purpose,
    normalize_email_verification_code,
    should_expose_dev_email_code,
)

__all__ = [
    "consume_email_verification_code",
    "generate_email_verification_code",
    "hash_email_verification_code",
    "issue_email_verification_code",
    "normalize_email_code_purpose",
    "normalize_email_verification_code",
    "should_expose_dev_email_code",
]
