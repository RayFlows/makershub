# app/shared/time/__init__.py
"""
时间工具包

当前提供统一的 UTC 当前时间函数，以及数据库适配层读取时间后补齐 UTC 时区的工具。
业务代码涉及过期时间、审计时间和流水时间时，应优先使用带时区的时间，避免本地时间
和数据库时间混用。
"""

from datetime import UTC, datetime


def utc_now() -> datetime:
    """返回带 UTC 时区的当前时间。"""

    return datetime.now(UTC)


def ensure_utc_datetime(value: datetime) -> datetime:
    """
    确保数据库读出的时间带 UTC 时区。

    SQLite 测试库会丢失 `DateTime(timezone=True)` 的 tzinfo；生产数据库也不应把 naive
    datetime 直接透出给端侧。这里统一把 naive 时间按 UTC 解释，接口展示如需北京时间由
    前端转换。
    """

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def ensure_optional_utc_datetime(value: datetime | None) -> datetime | None:
    """确保可空数据库时间带 UTC 时区。"""

    if value is None:
        return None
    return ensure_utc_datetime(value)


__all__ = ["ensure_optional_utc_datetime", "ensure_utc_datetime", "utc_now"]
