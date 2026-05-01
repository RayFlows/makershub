# app/infrastructure/email/client.py
"""
邮件发送适配器

本地开发使用 log 模式输出验证码，避免真实邮箱未准备好时阻塞身份流程。
生产环境切换到 smtp 模式后，本模块负责通过 SMTP 发送验证码邮件。
"""

from __future__ import annotations

import asyncio
import logging
import smtplib
from email.message import EmailMessage

from app.core.config.settings import get_settings
from app.core.errors import AppError

logger = logging.getLogger(__name__)


async def send_email_verification_code(
    *,
    email: str,
    purpose: str,
    code: str,
    expires_minutes: int,
) -> None:
    """
    发送邮箱验证码。

    Args:
        email: 收件邮箱。
        purpose: 验证码用途。
        code: 明文验证码，只允许在发送通道内短暂出现。
        expires_minutes: 验证码有效分钟数。
    """

    settings = get_settings()
    mode = settings.email_delivery_mode.lower()
    if mode == "log":
        if settings.app_env == "production":
            raise AppError(
                "EMAIL_LOG_MODE_FORBIDDEN",
                "生产环境不允许使用日志模式发送邮箱验证码",
                status_code=500,
            )
        logger.warning(
            "email verification code email=%s purpose=%s code=%s expires_minutes=%s",
            email,
            purpose,
            code,
            expires_minutes,
        )
        return

    if mode == "smtp":
        await asyncio.to_thread(
            send_email_verification_code_via_smtp,
            email=email,
            purpose=purpose,
            code=code,
            expires_minutes=expires_minutes,
        )
        return

    raise AppError("EMAIL_DELIVERY_MODE_INVALID", "邮件发送模式不合法", status_code=500)


def send_email_verification_code_via_smtp(
    *,
    email: str,
    purpose: str,
    code: str,
    expires_minutes: int,
) -> None:
    """通过 SMTP 发送验证码邮件。"""

    settings = get_settings()
    if not settings.smtp_host or not settings.smtp_username or not settings.smtp_password:
        raise AppError("SMTP_CONFIG_MISSING", "SMTP 配置缺失", status_code=500)

    from_email = settings.smtp_from_email or settings.smtp_username
    message = EmailMessage()
    message["Subject"] = "MakersHub 邮箱验证码"
    message["From"] = f"{settings.smtp_from_name} <{from_email}>"
    message["To"] = email
    message.set_content(
        "\n".join(
            [
                "你的 MakersHub 邮箱验证码如下：",
                "",
                code,
                "",
                f"验证码用途：{purpose}",
                f"有效期：{expires_minutes} 分钟",
                "",
                "如果不是你本人操作，请忽略这封邮件。",
            ]
        )
    )

    try:
        if settings.smtp_use_ssl:
            with smtplib.SMTP_SSL(settings.smtp_host, settings.smtp_port, timeout=10) as client:
                client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
        else:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=10) as client:
                client.starttls()
                client.login(settings.smtp_username, settings.smtp_password)
                client.send_message(message)
    except (OSError, smtplib.SMTPException) as exc:
        raise AppError("EMAIL_DELIVERY_FAILED", "验证码邮件发送失败", status_code=502) from exc
