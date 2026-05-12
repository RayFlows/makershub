# app/modules/points/utils.py
"""
积分账本校验与规范化工具

这些函数服务于积分域内部能力模块，负责金额、原因、业务标签和幂等键等基础校验。
业务链路仍然放在 accounts、ledger、holds、adjustments 等能力模块中。
"""

from __future__ import annotations

from app.core.errors import AppError
from app.modules.points.constants import POINT_ACCOUNT_ACTIVE, POINT_HOLD_ACTIVE
from app.modules.points.models import PointAccount, PointHold


def ensure_account_active(account: PointAccount) -> None:
    """确认账户可用于积分变动。"""

    if account.status != POINT_ACCOUNT_ACTIVE:
        raise AppError("POINT_ACCOUNT_DISABLED", "积分账户不可用", status_code=403)


def ensure_hold_active(hold: PointHold) -> None:
    """确认冻结记录仍可处理。"""

    if hold.status != POINT_HOLD_ACTIVE:
        raise AppError("POINT_HOLD_NOT_ACTIVE", "积分冻结记录已处理", status_code=409)


def ensure_available_balance(account: PointAccount, amount: int) -> None:
    """确认可用余额足够。"""

    if account.available_balance < amount:
        raise AppError("POINT_BALANCE_NOT_ENOUGH", "积分余额不足", status_code=409)


def ensure_frozen_balance(account: PointAccount, amount: int) -> None:
    """确认冻结余额足够。"""

    if account.frozen_balance < amount:
        raise AppError("POINT_ACCOUNT_INCONSISTENT", "积分冻结余额异常", status_code=500)


def normalize_positive_amount(amount: int) -> int:
    """校验正数积分数量。"""

    if amount <= 0:
        raise AppError("POINT_AMOUNT_INVALID", "积分数量必须大于 0", status_code=422)
    return amount


def normalize_required_label(value: str, *, field_label: str, max_length: int = 128) -> str:
    """清理必填短文本。"""

    normalized = value.strip()
    if not normalized:
        raise AppError("POINT_FIELD_REQUIRED", f"{field_label}不能为空", status_code=422)
    if len(normalized) > max_length:
        raise AppError("POINT_FIELD_TOO_LONG", f"{field_label}过长", status_code=422)
    return normalized


def normalize_idempotency_key(value: str) -> str:
    """清理幂等键。"""

    return normalize_required_label(value, field_label="幂等键", max_length=128)


def normalize_required_reason(value: str) -> str:
    """清理必填原因。"""

    normalized = normalize_optional_reason(value)
    if normalized is None:
        raise AppError("POINT_REASON_REQUIRED", "积分调整原因不能为空", status_code=422)
    return normalized


def normalize_optional_reason(value: str | None) -> str | None:
    """清理可选原因。"""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > 500:
        raise AppError("POINT_REASON_TOO_LONG", "积分操作原因过长", status_code=422)
    return normalized
