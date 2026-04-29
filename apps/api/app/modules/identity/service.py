from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.modules.identity.models import LocalAccount, User
from app.modules.identity.repository import IdentityRepository
from app.modules.organization.models import Position, UserPosition


@dataclass(frozen=True)
class BootstrapSuperAdminResult:
    user: User
    local_account: LocalAccount
    user_position: UserPosition
    created: bool


async def bootstrap_super_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str = "系统超级管理员",
) -> BootstrapSuperAdminResult:
    normalized_email = normalize_email(email)
    validate_initial_password(password)

    repository = IdentityRepository(session)
    existing_position = await repository.get_active_super_admin_position()
    existing_account = await repository.get_local_account_by_email(normalized_email)

    if existing_position is not None:
        raise AppError(
            "SUPER_ADMIN_ALREADY_EXISTS",
            "系统中已经存在有效的 999 超级管理员",
            status_code=409,
        )

    if existing_account is not None:
        raise AppError(
            "LOCAL_ACCOUNT_ALREADY_EXISTS",
            "该邮箱已经绑定本地账号",
            status_code=409,
        )

    position = await repository.get_position_by_code("999")
    if position is None:
        position = Position(
            code="999",
            name="超级管理员",
            status="active",
            sort_order=999,
            is_system=True,
        )
        session.add(position)
        await session.flush()

    user, local_account = await repository.create_local_user(
        email=normalized_email,
        password_hash=hash_password(password),
        display_name=display_name,
    )

    user_position = UserPosition(
        user_id=user.id,
        position_id=position.id,
        scope_type="global",
        scope_id=None,
        granted_by=None,
    )
    session.add(user_position)
    await session.flush()

    return BootstrapSuperAdminResult(
        user=user,
        local_account=local_account,
        user_position=user_position,
        created=True,
    )


def normalize_email(email: str) -> str:
    normalized = email.strip().lower()
    if "@" not in normalized:
        raise AppError("INVALID_EMAIL", "邮箱格式不合法", status_code=422)
    return normalized


def validate_initial_password(password: str) -> None:
    if len(password) < 8:
        raise AppError("PASSWORD_TOO_SHORT", "密码至少需要 8 位", status_code=422)
