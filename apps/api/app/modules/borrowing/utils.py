# app/modules/borrowing/utils.py
"""
借用域通用校验工具

借用状态机对文本、数量、审核动作和归还情况的要求比较集中，单独放在这里可以让
service.py 只表达业务流程，不被重复的字符串清洗代码淹没。
"""

from __future__ import annotations

from app.core.errors import AppError
from app.modules.borrowing.constants import (
    BORROW_RETURN_CONDITION_CONSUMED,
    BORROW_RETURN_CONDITION_DAMAGED,
    BORROW_RETURN_CONDITION_LOST,
    BORROW_RETURN_CONDITION_NORMAL,
    BORROW_REVIEW_APPROVE,
    BORROW_REVIEW_REJECT,
    BORROW_USAGE_PERSONAL,
    BORROW_USAGE_PROJECT,
)


def normalize_required_text(value: str | None, *, field_label: str, max_length: int) -> str:
    """规范化必填文本。"""

    text = (value or "").strip()
    if not text:
        raise AppError("BORROW_FIELD_REQUIRED", f"{field_label}不能为空", status_code=422)
    if len(text) > max_length:
        raise AppError("BORROW_FIELD_TOO_LONG", f"{field_label}不能超过 {max_length} 个字符", status_code=422)
    return text


def normalize_optional_text(value: str | None, *, field_label: str, max_length: int) -> str | None:
    """规范化可选文本。"""

    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > max_length:
        raise AppError("BORROW_FIELD_TOO_LONG", f"{field_label}不能超过 {max_length} 个字符", status_code=422)
    return text


def normalize_positive_quantity(value: int, *, field_label: str) -> int:
    """规范化正整数数量。"""

    if value <= 0:
        raise AppError("BORROW_QUANTITY_INVALID", f"{field_label}必须大于 0", status_code=422)
    return value


def normalize_usage_type(value: str) -> str:
    """规范化借用用途。"""

    normalized = normalize_required_text(value, field_label="借用用途", max_length=32)
    if normalized not in {BORROW_USAGE_PERSONAL, BORROW_USAGE_PROJECT}:
        raise AppError("BORROW_USAGE_TYPE_INVALID", "借用用途不合法", status_code=422)
    return normalized


def normalize_review_decision(value: str) -> str:
    """规范化审核动作。"""

    normalized = normalize_required_text(value, field_label="审核动作", max_length=32)
    if normalized not in {BORROW_REVIEW_APPROVE, BORROW_REVIEW_REJECT}:
        raise AppError("BORROW_REVIEW_DECISION_INVALID", "审核动作不合法", status_code=422)
    return normalized


def normalize_return_condition(value: str) -> str:
    """规范化归还情况。"""

    normalized = normalize_required_text(value, field_label="归还情况", max_length=32)
    if normalized not in {
        BORROW_RETURN_CONDITION_NORMAL,
        BORROW_RETURN_CONDITION_DAMAGED,
        BORROW_RETURN_CONDITION_LOST,
        BORROW_RETURN_CONDITION_CONSUMED,
    }:
        raise AppError("BORROW_RETURN_CONDITION_INVALID", "归还情况不合法", status_code=422)
    return normalized
