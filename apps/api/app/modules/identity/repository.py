from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.identity.models import LocalAccount, User
from app.modules.organization.models import Position, UserPosition


class IdentityRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_local_account_by_email(self, email: str) -> LocalAccount | None:
        statement = select(LocalAccount).where(func.lower(LocalAccount.email) == email.lower())
        return await self.session.scalar(statement)

    async def get_active_super_admin_position(self) -> UserPosition | None:
        statement = (
            select(UserPosition)
            .join(Position, UserPosition.position_id == Position.id)
            .where(Position.code == "999", UserPosition.revoked_at.is_(None))
        )
        return await self.session.scalar(statement)

    async def get_position_by_code(self, code: str) -> Position | None:
        statement = select(Position).where(Position.code == code)
        return await self.session.scalar(statement)

    async def create_local_user(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> tuple[User, LocalAccount]:
        from datetime import UTC, datetime

        now = datetime.now(UTC)
        user = User(display_name=display_name, status="active")
        account = LocalAccount(
            user=user,
            email=email,
            password_hash=password_hash,
            password_set_at=now,
            email_verified_at=now,
            status="active",
        )
        self.session.add(user)
        self.session.add(account)
        await self.session.flush()
        return user, account
