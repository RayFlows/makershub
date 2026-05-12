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
from app.modules.points.ledger.repository import PointLedgerRepository
from app.modules.points.models import PointAccount, PointLedgerEntry
from app.modules.points.types import PointLedgerPage, PointOperationResult


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
