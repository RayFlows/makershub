# app/modules/points/accounts/repository.py
"""
积分账户仓储

本文件只封装 point_accounts 的查询与创建。账户能否发生余额变动由服务层判断，
仓储层不提交事务，也不决定业务规则。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.points.constants import POINT_ACCOUNT_ACTIVE
from app.modules.points.models import PointAccount


class PointAccountRepository:
    """积分账户仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_account_by_user_id(self, user_id: int, *, for_update: bool = False) -> PointAccount | None:
        """按用户 ID 查询积分账户。"""

        statement = select(PointAccount).where(PointAccount.user_id == user_id)
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def create_account(self, *, user_id: int) -> PointAccount:
        """为用户创建 0 积分账户。"""

        account = PointAccount(user_id=user_id, balance=0, frozen_balance=0, status=POINT_ACCOUNT_ACTIVE)
        self.session.add(account)
        await self.session.flush()
        await self.session.refresh(account)
        return account
