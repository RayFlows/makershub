# app/modules/points/ledger/repository.py
"""
积分流水仓储

本文件只封装 point_ledger_entries 的查询和写入。流水是积分事实来源，但余额如何变化
由调用方服务层在写入流水前完成。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.points.models import PointLedgerEntry


class PointLedgerRepository:
    """积分流水仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_ledger_entry_by_idempotency_key(self, idempotency_key: str) -> PointLedgerEntry | None:
        """按幂等键查询积分流水。"""

        statement = select(PointLedgerEntry).where(PointLedgerEntry.idempotency_key == idempotency_key)
        return await self.session.scalar(statement)

    async def add_ledger_entry(self, entry: PointLedgerEntry) -> PointLedgerEntry:
        """写入一条积分流水。"""

        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_ledger_entries(
        self,
        *,
        page: int,
        page_size: int,
        user_id: int | None = None,
    ) -> tuple[list[PointLedgerEntry], int]:
        """分页查询积分流水。"""

        conditions = []
        if user_id is not None:
            conditions.append(PointLedgerEntry.user_id == user_id)

        statement = (
            select(PointLedgerEntry)
            .where(*conditions)
            .order_by(PointLedgerEntry.created_at.desc(), PointLedgerEntry.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(PointLedgerEntry.id)).where(*conditions)
        entries = list((await self.session.scalars(statement)).all())
        total = await self.session.scalar(count_statement)
        return entries, total or 0
