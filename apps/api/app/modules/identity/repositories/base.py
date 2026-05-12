# app/modules/identity/repositories/base.py
"""
身份域基础仓储能力

这里放用户主体、职务查询和最近登录时间刷新等多条身份链路都会复用的查询。
能力子模块不要直接创建数据库会话，只复用本基类持有的 AsyncSession。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models import User
from app.modules.organization.models import Position, UserPosition
from app.shared.time import utc_now


class IdentityRepositoryBase:
    """身份域仓储基类。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_user_by_id(self, user_id: int) -> User | None:
        """按内部用户主键查找用户主体。"""

        statement = select(User).options(selectinload(User.email_password_account)).where(User.id == user_id)
        return await self.session.scalar(statement)

    async def mark_user_login(self, user: User) -> User:
        """刷新用户最近登录时间。"""

        user.last_login_at = utc_now()
        await self.session.flush()
        return user

    async def get_active_super_admin_position(self) -> UserPosition | None:
        """查找当前系统中是否已经存在有效 999。"""

        statement = (
            select(UserPosition)
            .join(Position, UserPosition.position_id == Position.id)
            .where(Position.code == "999", UserPosition.revoked_at.is_(None))
        )
        return await self.session.scalar(statement)

    async def get_position_by_code(self, code: str) -> Position | None:
        """按职务代码查找职务定义。"""

        statement = select(Position).where(Position.code == code)
        return await self.session.scalar(statement)
