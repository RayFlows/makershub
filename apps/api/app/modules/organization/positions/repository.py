# app/modules/organization/positions/repository.py
"""
职务仓储

本文件封装 positions 和 user_positions 的查询写入。普通协会职务和 998/999 系统身份
使用同一张事实表，但服务层会限制普通成员接口不能维护系统身份。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.organization.models import Position, UserPosition
from app.shared.time import utc_now


class PositionRepository:
    """职务和用户职务关系仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_positions(self, *, active_only: bool = True, include_system: bool = False) -> list[Position]:
        """列出职务定义。"""

        statement = select(Position).order_by(Position.sort_order.asc(), Position.id.asc())
        if active_only:
            statement = statement.where(Position.status == "active")
        if not include_system:
            statement = statement.where(Position.is_system.is_(False))
        return list((await self.session.scalars(statement)).all())

    async def get_position_by_code(self, code: str) -> Position | None:
        """按稳定 code 查询职务定义。"""

        statement = select(Position).where(Position.code == code)
        return await self.session.scalar(statement)

    async def list_user_positions(self, user_id: int, *, include_system: bool = False) -> list[UserPosition]:
        """列出用户当前有效职务。"""

        statement = (
            select(UserPosition)
            .join(Position, Position.id == UserPosition.position_id)
            .options(selectinload(UserPosition.position), selectinload(UserPosition.department))
            .where(UserPosition.user_id == user_id, UserPosition.revoked_at.is_(None))
            .order_by(Position.sort_order.asc(), UserPosition.id.asc())
        )
        if not include_system:
            statement = statement.where(Position.is_system.is_(False))
        return list((await self.session.scalars(statement)).all())

    async def list_active_user_positions_by_user_ids(
        self,
        user_ids: list[int],
        *,
        include_system: bool = False,
    ) -> list[UserPosition]:
        """批量列出多个用户当前有效职务。"""

        if not user_ids:
            return []
        statement = (
            select(UserPosition)
            .join(Position, Position.id == UserPosition.position_id)
            .options(selectinload(UserPosition.position), selectinload(UserPosition.department))
            .where(UserPosition.user_id.in_(user_ids), UserPosition.revoked_at.is_(None))
            .order_by(UserPosition.user_id.asc(), Position.sort_order.asc())
        )
        if not include_system:
            statement = statement.where(Position.is_system.is_(False))
        return list((await self.session.scalars(statement)).all())

    async def grant_user_position(
        self,
        *,
        user_id: int,
        position: Position,
        granted_by: int | None,
        department_id: int | None = None,
        scope_type: str = "global",
        scope_id: int | None = None,
    ) -> UserPosition:
        """授予用户一个职务，已存在相同有效职务时保持幂等。"""

        existing = await self.session.scalar(
            select(UserPosition)
            .options(selectinload(UserPosition.position), selectinload(UserPosition.department))
            .where(
                UserPosition.user_id == user_id,
                UserPosition.position_id == position.id,
                UserPosition.department_id == department_id,
                UserPosition.scope_type == scope_type,
                UserPosition.scope_id == scope_id,
                UserPosition.revoked_at.is_(None),
            )
        )
        if existing is not None:
            return existing

        user_position = UserPosition(
            user_id=user_id,
            position=position,
            department_id=department_id,
            scope_type=scope_type,
            scope_id=scope_id,
            granted_by=granted_by,
            granted_at=utc_now(),
        )
        self.session.add(user_position)
        return user_position

    async def revoke_user_position(self, user_position: UserPosition) -> UserPosition:
        """撤销用户职务，保留历史记录。"""

        user_position.revoked_at = utc_now()
        return user_position
