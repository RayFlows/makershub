# app/modules/points/holds/repository.py
"""
积分冻结仓储

本文件封装 point_holds 的查询和写入。冻结生命周期是否允许流转由 holds 服务判断，
仓储层不提交事务。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.points.constants import POINT_HOLD_ACTIVE
from app.modules.points.models import PointHold


class PointHoldRepository:
    """积分冻结记录仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_hold_by_id(self, hold_id: int, *, for_update: bool = False) -> PointHold | None:
        """按 ID 查询冻结记录。"""

        statement = select(PointHold).where(PointHold.id == hold_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def get_hold_by_idempotency_key(self, idempotency_key: str) -> PointHold | None:
        """按幂等键查询冻结记录。"""

        statement = select(PointHold).where(PointHold.idempotency_key == idempotency_key)
        return await self.session.scalar(statement)

    async def get_active_hold_by_business(
        self,
        *,
        business_type: str,
        business_id: str,
    ) -> PointHold | None:
        """按业务来源查询有效冻结记录。"""

        statement = select(PointHold).where(
            PointHold.business_type == business_type,
            PointHold.business_id == business_id,
            PointHold.status == POINT_HOLD_ACTIVE,
        )
        return await self.session.scalar(statement)

    async def add_hold(self, hold: PointHold) -> PointHold:
        """写入一条冻结记录。"""

        self.session.add(hold)
        await self.session.flush()
        return hold
