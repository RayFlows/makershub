# app/modules/points/holds/service.py
"""
积分冻结服务

本文件处理冻结、解冻和冻结转扣除。冻结记录服务借用押金、打印接单预扣等业务，
但这里不判断具体业务是否通过审核，只维护积分账本事实。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.points.accounts import get_or_create_point_account
from app.modules.points.constants import (
    POINT_DIRECTION_FREEZE,
    POINT_DIRECTION_HOLD_DEDUCT,
    POINT_DIRECTION_UNFREEZE,
    POINT_HOLD_ACTIVE,
    POINT_HOLD_DEDUCTED,
    POINT_HOLD_RELEASED,
)
from app.modules.points.holds.repository import PointHoldRepository
from app.modules.points.ledger import append_ledger_entry, get_existing_idempotent_result
from app.modules.points.models import PointHold
from app.modules.points.types import PointOperationResult
from app.modules.points.utils import (
    ensure_account_active,
    ensure_available_balance,
    ensure_frozen_balance,
    ensure_hold_active,
    normalize_idempotency_key,
    normalize_optional_reason,
    normalize_positive_amount,
    normalize_required_label,
)
from app.shared.time import utc_now


async def freeze_points(
    session: AsyncSession,
    *,
    user_id: int,
    amount: int,
    business_type: str,
    business_id: str,
    idempotency_key: str,
    reason: str | None = None,
    operator_id: int | None = None,
) -> PointOperationResult:
    """
    冻结用户积分。

    冻结不扣减总余额，只增加 frozen_balance。后续业务可以调用 release_point_hold 解冻，
    或 deduct_point_hold 把冻结积分转为实际扣除。
    """

    normalized_amount = normalize_positive_amount(amount)
    normalized_business_type = normalize_required_label(business_type, field_label="业务类型")
    normalized_business_id = normalize_required_label(business_id, field_label="业务 ID")
    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    normalized_reason = normalize_optional_reason(reason)

    existing = await get_existing_idempotent_result(
        session,
        idempotency_key=normalized_idempotency_key,
        user_id=user_id,
        business_type=normalized_business_type,
    )
    if existing is not None:
        return existing

    account = await get_or_create_point_account(session, user_id=user_id, for_update=True)
    ensure_account_active(account)
    ensure_available_balance(account, normalized_amount)
    account.frozen_balance += normalized_amount

    repository = PointHoldRepository(session)
    hold = PointHold(
        account_id=account.id,
        user_id=user_id,
        amount=normalized_amount,
        business_type=normalized_business_type,
        business_id=normalized_business_id,
        idempotency_key=normalized_idempotency_key,
        status=POINT_HOLD_ACTIVE,
        reason=normalized_reason,
        created_by=operator_id,
    )
    hold = await repository.add_hold(hold)
    entry = await append_ledger_entry(
        session,
        account=account,
        direction=POINT_DIRECTION_FREEZE,
        amount=normalized_amount,
        business_type=normalized_business_type,
        business_id=normalized_business_id,
        idempotency_key=normalized_idempotency_key,
        reason=normalized_reason,
        operator_id=operator_id,
        related_hold_id=hold.id,
    )
    return PointOperationResult(account=account, ledger_entry=entry, hold=hold)


async def release_point_hold(
    session: AsyncSession,
    *,
    hold_id: int,
    idempotency_key: str,
    reason: str | None = None,
    operator_id: int | None = None,
) -> PointOperationResult:
    """解冻一条有效冻结记录。"""

    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    existing = await get_existing_idempotent_result(session, idempotency_key=normalized_idempotency_key)
    if existing is not None:
        return existing

    repository = PointHoldRepository(session)
    hold = await repository.get_hold_by_id(hold_id, for_update=True)
    if hold is None:
        raise AppError("POINT_HOLD_NOT_FOUND", "积分冻结记录不存在", status_code=404)
    ensure_hold_active(hold)

    account = await get_or_create_point_account(session, user_id=hold.user_id, for_update=True)
    ensure_account_active(account)
    ensure_frozen_balance(account, hold.amount)
    account.frozen_balance -= hold.amount
    hold.status = POINT_HOLD_RELEASED
    hold.released_at = utc_now()

    entry = await append_ledger_entry(
        session,
        account=account,
        direction=POINT_DIRECTION_UNFREEZE,
        amount=hold.amount,
        business_type=hold.business_type,
        business_id=hold.business_id,
        idempotency_key=normalized_idempotency_key,
        reason=normalize_optional_reason(reason) or hold.reason,
        operator_id=operator_id,
        related_hold_id=hold.id,
    )
    return PointOperationResult(account=account, ledger_entry=entry, hold=hold)


async def deduct_point_hold(
    session: AsyncSession,
    *,
    hold_id: int,
    idempotency_key: str,
    reason: str | None = None,
    operator_id: int | None = None,
) -> PointOperationResult:
    """把一条有效冻结记录转为实际扣除。"""

    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    existing = await get_existing_idempotent_result(session, idempotency_key=normalized_idempotency_key)
    if existing is not None:
        return existing

    repository = PointHoldRepository(session)
    hold = await repository.get_hold_by_id(hold_id, for_update=True)
    if hold is None:
        raise AppError("POINT_HOLD_NOT_FOUND", "积分冻结记录不存在", status_code=404)
    ensure_hold_active(hold)

    account = await get_or_create_point_account(session, user_id=hold.user_id, for_update=True)
    ensure_account_active(account)
    ensure_frozen_balance(account, hold.amount)
    account.frozen_balance -= hold.amount
    account.balance -= hold.amount
    hold.status = POINT_HOLD_DEDUCTED
    hold.deducted_at = utc_now()

    entry = await append_ledger_entry(
        session,
        account=account,
        direction=POINT_DIRECTION_HOLD_DEDUCT,
        amount=hold.amount,
        business_type=hold.business_type,
        business_id=hold.business_id,
        idempotency_key=normalized_idempotency_key,
        reason=normalize_optional_reason(reason) or hold.reason,
        operator_id=operator_id,
        related_hold_id=hold.id,
    )
    return PointOperationResult(account=account, ledger_entry=entry, hold=hold)
