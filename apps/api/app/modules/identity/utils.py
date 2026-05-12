# app/modules/identity/utils.py
"""
身份域通用校验工具

本文件只放多个身份能力都会复用的小工具。具体业务用例仍放在 accounts、
email_codes、sessions 和 bootstrap 子模块中，避免再次形成巨大的 service.py。
"""

from __future__ import annotations

from datetime import UTC, datetime

from app.core.errors import AppError


def normalize_email(email: str) -> str:
    """规范化邮箱登录名。"""

    normalized = email.strip().lower()
    if "@" not in normalized or len(normalized) > 255:
        raise AppError("INVALID_EMAIL", "邮箱格式不合法", status_code=422)
    return normalized


def normalize_wechat_identifier(value: str, *, field_name: str) -> str:
    """规范化微信返回的 openid/unionid。"""

    normalized = value.strip()
    if not normalized:
        raise AppError("INVALID_WECHAT_IDENTIFIER", f"{field_name} 不能为空", status_code=422)
    return normalized


def validate_initial_password(password: str) -> None:
    """校验初始化 999 使用的邮箱密码。"""

    validate_password(password)


def validate_password(password: str) -> None:
    """校验邮箱密码复杂度底线。"""

    if len(password) < 8:
        raise AppError("PASSWORD_TOO_SHORT", "密码至少需要 8 位", status_code=422)


def trim_optional_text(value: str | None, *, max_length: int) -> str | None:
    """裁剪可选文本，避免请求头等客户端输入超过数据库字段长度。"""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:max_length]


def ensure_aware_datetime(value: datetime) -> datetime:
    """确保数据库时间可以和 UTC 当前时间比较。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value
