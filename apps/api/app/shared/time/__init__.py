# app/shared/time/__init__.py
"""
时间工具包

当前先提供统一的 UTC 当前时间函数。业务代码涉及过期时间、审计时间和流水时间时，
应优先使用带时区的时间，避免本地时间和数据库时间混用。
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""

    return datetime.now(UTC)


__all__ = ["utc_now"]
