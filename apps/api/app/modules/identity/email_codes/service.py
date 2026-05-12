# app/modules/identity/email_codes/service.py
"""
邮箱验证码服务

本文件负责验证码用途校验、发送频率限制、验证码哈希和消费逻辑。它不直接发送邮件，
实际投递由 infrastructure/email 完成。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.modules.identity.models import EmailVerificationCode
from app.modules.identity.repositories import IdentityRepository
from app.modules.identity.types import EmailVerificationIssueResult
from app.modules.identity.utils import ensure_aware_datetime, normalize_email, trim_optional_text
from app.shared.time import utc_now


async def issue_email_verification_code(
    session: AsyncSession,
    *,
    email: str,
    purpose: str,
    user_id: int | None,
    request_ip: str | None = None,
) -> tuple[EmailVerificationIssueResult, str]:
    """生成并保存邮箱验证码。

    本函数只负责验证码规则和落库，真正发送由 infrastructure/email 完成。
    """

    normalized_email = normalize_email(email)
    normalized_purpose = normalize_email_code_purpose(purpose)
    settings = get_settings()
    now = utc_now()
    repository = IdentityRepository(session)

    if normalized_purpose == "bind_email":
        if user_id is None:
            raise AppError("AUTH_REQUIRED_FOR_EMAIL_BIND", "绑定邮箱需要先登录", status_code=401)
        existing_account = await repository.get_email_password_account_by_email(normalized_email)
        if existing_account is not None and existing_account.user_id != user_id:
            raise AppError("EMAIL_ALREADY_BOUND", "该邮箱已经绑定其他用户", status_code=409)
        code_user_id = user_id
    elif normalized_purpose == "first_login":
        existing_account = await repository.get_email_password_account_by_email(normalized_email)
        if existing_account is None or existing_account.status != "active":
            raise AppError("EMAIL_PASSWORD_ACCOUNT_NOT_FOUND", "该邮箱尚未绑定账号", status_code=404)
        if existing_account.password_hash is not None:
            raise AppError("FIRST_LOGIN_NOT_REQUIRED", "该邮箱已设置密码，请使用密码登录", status_code=409)
        code_user_id = existing_account.user_id
    else:
        code_user_id = user_id

    latest = await repository.get_latest_email_verification_code(
        email=normalized_email,
        purpose=normalized_purpose,
        user_id=code_user_id,
    )
    if latest is not None:
        latest_created_at = ensure_aware_datetime(latest.created_at)
        elapsed_seconds = (now - latest_created_at).total_seconds()
        if elapsed_seconds < settings.email_code_resend_interval_seconds:
            retry_after = max(1, int(settings.email_code_resend_interval_seconds - elapsed_seconds))
            raise AppError(
                "EMAIL_CODE_TOO_FREQUENT",
                "验证码请求过于频繁",
                status_code=429,
                details={"retry_after_seconds": retry_after},
            )

    sent_count = await repository.count_email_verification_codes_since(
        email=normalized_email,
        purpose=normalized_purpose,
        since=now - timedelta(hours=1),
    )
    if sent_count >= settings.email_code_hourly_limit:
        raise AppError(
            "EMAIL_CODE_HOURLY_LIMIT_EXCEEDED",
            "该邮箱验证码发送次数已达上限",
            status_code=429,
        )

    code = generate_email_verification_code()
    expires_at = now + timedelta(minutes=settings.email_code_expire_minutes)
    await repository.create_email_verification_code(
        email=normalized_email,
        purpose=normalized_purpose,
        code_hash=hash_email_verification_code(
            email=normalized_email,
            purpose=normalized_purpose,
            code=code,
        ),
        expires_at=expires_at,
        request_ip=trim_optional_text(request_ip, max_length=64),
        user_id=code_user_id,
    )
    result = EmailVerificationIssueResult(
        email=normalized_email,
        purpose=normalized_purpose,
        expires_at=expires_at,
        delivery_mode=settings.email_delivery_mode.lower(),
        dev_code=code if should_expose_dev_email_code() else None,
    )
    return result, code


async def consume_email_verification_code(
    session: AsyncSession,
    *,
    email: str,
    purpose: str,
    code: str,
    user_id: int | None,
) -> EmailVerificationCode:
    """校验并消费邮箱验证码。"""

    normalized_email = normalize_email(email)
    normalized_purpose = normalize_email_code_purpose(purpose)
    normalized_code = normalize_email_verification_code(code)
    repository = IdentityRepository(session)
    record = await repository.get_usable_email_verification_code(
        email=normalized_email,
        purpose=normalized_purpose,
        code_hash=hash_email_verification_code(
            email=normalized_email,
            purpose=normalized_purpose,
            code=normalized_code,
        ),
        user_id=user_id,
        now=utc_now(),
    )
    if record is None:
        raise AppError("EMAIL_CODE_INVALID_OR_EXPIRED", "验证码无效或已过期", status_code=422)

    await repository.consume_email_verification_code(record)
    return record


def normalize_email_code_purpose(purpose: str) -> str:
    """规范化邮箱验证码用途。"""

    normalized = purpose.strip().lower()
    if normalized not in {"bind_email", "first_login"}:
        raise AppError("EMAIL_CODE_PURPOSE_UNSUPPORTED", "当前验证码用途暂未支持", status_code=422)
    return normalized


def normalize_email_verification_code(code: str) -> str:
    """规范化用户提交的邮箱验证码。"""

    normalized = code.strip()
    if len(normalized) != 6 or not normalized.isdigit():
        raise AppError("EMAIL_CODE_FORMAT_INVALID", "验证码格式不合法", status_code=422)
    return normalized


def generate_email_verification_code() -> str:
    """生成 6 位数字邮箱验证码。"""

    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_verification_code(*, email: str, purpose: str, code: str) -> str:
    """计算邮箱验证码哈希。"""

    settings = get_settings()
    message = f"{purpose}:{email}:{code}".encode()
    return hmac.new(settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def should_expose_dev_email_code() -> bool:
    """本地和测试环境是否允许在响应中暴露验证码。"""

    settings = get_settings()
    return settings.app_env in {"local", "test", "development"} and settings.email_delivery_mode.lower() == "log"
