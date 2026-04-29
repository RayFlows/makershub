# app/infrastructure/email/__init__.py
"""
邮件基础设施适配导出

验证码业务只关心“验证码是否已经交给发送通道”，不直接操作 SMTP。
"""

from app.infrastructure.email.client import send_email_verification_code

__all__ = ["send_email_verification_code"]
