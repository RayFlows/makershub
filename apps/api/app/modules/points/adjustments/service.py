# app/modules/points/adjustments/service.py
"""
人工积分调整服务

本文件处理受控人工补发和扣减。它只维护账本事实；是否允许某个操作者执行调整、
是否需要会议记录或审批，由接口层和后续规则审批能力负责。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.points.accounts import get_or_create_point_account
from app.modules.points.constants import POINT_DIRECTION_EXPENSE, POINT_DIRECTION_INCOME
from app.modules.points.ledger import append_ledger_entry, get_existing_idempotent_result
from app.modules.points.types import PointOperationResult
from app.modules.points.utils import (
    ensure_account_active,
    ensure_available_balance,
    normalize_idempotency_key,
    normalize_required_reason,
)


async def manually_adjust_points(
    session: AsyncSession,
    *,
    user_id: int,
    amount: int,
    reason: str,
    operator_id: int,
    idempotency_key: str,
    business_id: str | None = None,
) -> PointOperationResult:
    """
    受控人工调整积分。

    amount 为正表示补发/奖励，为负表示扣减。人工调整必须填写原因，并由 HTTP 层写入
    审计日志；这里负责账本事实本身。
    """

    normalized_reason = normalize_required_reason(reason)
    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    direction = POINT_DIRECTION_INCOME if amount > 0 else POINT_DIRECTION_EXPENSE
    normalized_amount = abs(amount)
    if normalized_amount <= 0:
        raise AppError("POINT_AMOUNT_INVALID", "积分变动数量必须不为 0", status_code=422)

    existing = await get_existing_idempotent_result(
        session,
        idempotency_key=normalized_idempotency_key,
        user_id=user_id,
        business_type="manual_adjustment",
    )
    if existing is not None:
        return existing

    account = await get_or_create_point_account(session, user_id=user_id, for_update=True)
    ensure_account_active(account)

    if direction == POINT_DIRECTION_INCOME:
        account.balance += normalized_amount
    else:
        ensure_available_balance(account, normalized_amount)
        account.balance -= normalized_amount

    entry = await append_ledger_entry(
        session,
        account=account,
        direction=direction,
        amount=normalized_amount,
        business_type="manual_adjustment",
        business_id=business_id,
        idempotency_key=normalized_idempotency_key,
        reason=normalized_reason,
        operator_id=operator_id,
    )
    return PointOperationResult(account=account, ledger_entry=entry)
