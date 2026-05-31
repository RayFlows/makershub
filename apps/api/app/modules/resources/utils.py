# app/modules/resources/utils.py
"""
资源域通用校验工具

这些函数只处理资源域内部的文本、数量和状态规范化。权限、借用审批和积分押金
由各自业务域负责，避免工具函数承担过多业务含义。
"""

from __future__ import annotations

from app.core.errors import AppError


def normalize_required_text(value: str | None, *, field_label: str, max_length: int) -> str:
    """规范化必填文本。"""

    text = (value or "").strip()
    if not text:
        raise AppError("RESOURCE_FIELD_REQUIRED", f"{field_label}不能为空", status_code=422)
    if len(text) > max_length:
        raise AppError("RESOURCE_FIELD_TOO_LONG", f"{field_label}不能超过 {max_length} 个字符", status_code=422)
    return text


def normalize_optional_text(value: str | None, *, field_label: str, max_length: int) -> str | None:
    """规范化可选文本。"""

    if value is None:
        return None
    text = value.strip()
    if not text:
        return None
    if len(text) > max_length:
        raise AppError("RESOURCE_FIELD_TOO_LONG", f"{field_label}不能超过 {max_length} 个字符", status_code=422)
    return text


def normalize_non_negative_int(value: int, *, field_label: str) -> int:
    """规范化非负整数。"""

    if value < 0:
        raise AppError("RESOURCE_NUMBER_INVALID", f"{field_label}不能为负数", status_code=422)
    return value


def ensure_available_not_greater_than_total(*, total_quantity: int, available_quantity: int) -> None:
    """确保可借库存不超过账面总量。"""

    if available_quantity > total_quantity:
        raise AppError("MATERIAL_STOCK_INVALID", "可借数量不能大于总数量", status_code=422)
