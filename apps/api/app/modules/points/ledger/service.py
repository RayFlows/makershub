# app/modules/points/ledger/service.py
"""
积分流水服务

本文件负责分页读取流水、追加余额快照，以及根据幂等键恢复已有操作结果。它不负责
决定余额如何变化；余额变化由人工调整、冻结等具体能力先完成，再调用这里追加流水。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.points.accounts.repository import PointAccountRepository
from app.modules.points.accounts.service import ensure_user_exists
from app.modules.points.constants import (
    POINT_DIRECTION_EXPENSE,
    POINT_DIRECTION_HOLD_DEDUCT,
    POINT_DIRECTION_INCOME,
    POINT_DIRECTION_REVERSAL,
)
from app.modules.points.ledger.repository import PointLedgerRepository
from app.modules.points.models import PointAccount, PointLedgerEntry
from app.modules.points.types import PointLedgerPage, PointOperationResult
from app.modules.points.utils import (
    ensure_account_active,
    ensure_available_balance,
    normalize_idempotency_key,
    normalize_required_reason,
)


async def list_point_ledger_entries(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    user_id: int | None = None,
) -> PointLedgerPage:
    """分页查询积分流水。"""

    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    if user_id is not None:
        await ensure_user_exists(session, user_id=user_id)

    repository = PointLedgerRepository(session)
    entries, total = await repository.list_ledger_entries(
        page=normalized_page,
        page_size=normalized_page_size,
        user_id=user_id,
    )
    return PointLedgerPage(
        items=entries,
        page=normalized_page,
        page_size=normalized_page_size,
        total=total,
    )


async def append_ledger_entry(
    session: AsyncSession,
    *,
    account: PointAccount,
    direction: str,
    amount: int,
    business_type: str,
    business_id: str | None,
    idempotency_key: str,
    reason: str | None,
    operator_id: int | None,
    related_hold_id: int | None = None,
) -> PointLedgerEntry:
    """按账户当前余额追加一条流水。"""

    repository = PointLedgerRepository(session)
    entry = PointLedgerEntry(
        account_id=account.id,
        user_id=account.user_id,
        direction=direction,
        amount=amount,
        balance_after=account.balance,
        available_balance_after=account.available_balance,
        frozen_balance_after=account.frozen_balance,
        business_type=business_type,
        business_id=business_id,
        idempotency_key=idempotency_key,
        related_hold_id=related_hold_id,
        reason=reason,
        operator_id=operator_id,
    )
    entry = await repository.add_ledger_entry(entry)
    await session.refresh(account)
    return entry


async def get_existing_idempotent_result(
    session: AsyncSession,
    *,
    idempotency_key: str,
    user_id: int | None = None,
    business_type: str | None = None,
) -> PointOperationResult | None:
    """根据幂等键返回已有操作结果。"""

    ledger_repository = PointLedgerRepository(session)
    existing_entry = await ledger_repository.get_ledger_entry_by_idempotency_key(idempotency_key)
    if existing_entry is None:
        return None
    if user_id is not None and existing_entry.user_id != user_id:
        raise AppError("POINT_IDEMPOTENCY_CONFLICT", "幂等键已被其他用户操作使用", status_code=409)
    if business_type is not None and existing_entry.business_type != business_type:
        raise AppError("POINT_IDEMPOTENCY_CONFLICT", "幂等键已被其他业务操作使用", status_code=409)

    account_repository = PointAccountRepository(session)
    account = await account_repository.get_account_by_user_id(existing_entry.user_id)
    if account is None:
        raise AppError("POINT_ACCOUNT_NOT_FOUND", "积分账户不存在", status_code=500)
    hold = None
    if existing_entry.related_hold_id is not None:
        from app.modules.points.holds.repository import PointHoldRepository

        hold_repository = PointHoldRepository(session)
        hold = await hold_repository.get_hold_by_id(existing_entry.related_hold_id)
    return PointOperationResult(account=account, ledger_entry=existing_entry, hold=hold, idempotent=True)


async def reverse_ledger_entry(
    session: AsyncSession,
    *,
    ledger_entry_id: int,
    reason: str,
    operator_id: int,
    idempotency_key: str,
) -> PointOperationResult:
    """
    通过追加反向流水修正一条既有积分流水。

    反向修正不删除原流水，也不覆盖原余额快照。当前支持撤回奖励类流水，以及撤回普通
    扣分/冻结转扣除流水；冻结和解冻流水涉及冻结状态机，必须由 holds 能力单独处理。
    """

    normalized_reason = normalize_required_reason(reason)
    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    existing = await get_existing_idempotent_result(
        session,
        idempotency_key=normalized_idempotency_key,
        business_type="ledger_reversal",
    )
    if existing is not None:
        return existing

    repository = PointLedgerRepository(session)
    original_entry = await repository.get_ledger_entry_by_id(ledger_entry_id)
    if original_entry is None:
        raise AppError("POINT_LEDGER_NOT_FOUND", "积分流水不存在", status_code=404)
    if original_entry.direction == POINT_DIRECTION_REVERSAL:
        raise AppError("POINT_LEDGER_REVERSAL_UNSUPPORTED", "反向修正流水不能再次反向修正", status_code=409)
    if original_entry.direction not in {
        POINT_DIRECTION_INCOME,
        POINT_DIRECTION_EXPENSE,
        POINT_DIRECTION_HOLD_DEDUCT,
    }:
        raise AppError("POINT_LEDGER_REVERSAL_UNSUPPORTED", "该类型流水暂不支持直接反向修正", status_code=409)

    existing_reversal = await repository.get_ledger_entry_by_business(
        business_type="ledger_reversal",
        business_id=str(original_entry.id),
    )
    if existing_reversal is not None:
        raise AppError("POINT_LEDGER_ALREADY_REVERSED", "该积分流水已经存在反向修正", status_code=409)

    account_repository = PointAccountRepository(session)
    account = await account_repository.get_account_by_user_id(original_entry.user_id, for_update=True)
    if account is None:
        raise AppError("POINT_ACCOUNT_NOT_FOUND", "积分账户不存在", status_code=500)
    ensure_account_active(account)

    if original_entry.direction == POINT_DIRECTION_INCOME:
        ensure_available_balance(account, original_entry.amount)
        account.balance -= original_entry.amount
    else:
        account.balance += original_entry.amount

    entry = await append_ledger_entry(
        session,
        account=account,
        direction=POINT_DIRECTION_REVERSAL,
        amount=original_entry.amount,
        business_type="ledger_reversal",
        business_id=str(original_entry.id),
        idempotency_key=normalized_idempotency_key,
        reason=normalized_reason,
        operator_id=operator_id,
    )
    return PointOperationResult(account=account, ledger_entry=entry)
