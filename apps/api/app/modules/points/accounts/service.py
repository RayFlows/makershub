# app/modules/points/accounts/service.py
"""
积分账户服务

本文件负责积分账户的读取和懒创建。每个用户都应该有积分账户，但第一阶段允许历史
数据和新微信用户在首次查看或首次发生积分操作时再创建账户。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.identity.repositories import IdentityRepository
from app.modules.points.accounts.repository import PointAccountRepository
from app.modules.points.models import PointAccount


async def get_or_create_point_account(
    session: AsyncSession,
    *,
    user_id: int,
    for_update: bool = False,
) -> PointAccount:
    """
    获取或创建用户积分账户。

    每个用户都应该有积分账户。为了让旧数据和新微信用户都能平滑进入账本系统，
    第一阶段采用懒创建：首次查看或发生积分变动时自动创建 0 积分账户。
    """

    await ensure_user_exists(session, user_id=user_id)
    repository = PointAccountRepository(session)
    account = await repository.get_account_by_user_id(user_id, for_update=for_update)
    if account is not None:
        return account
    return await repository.create_account(user_id=user_id)


async def ensure_user_exists(session: AsyncSession, *, user_id: int) -> None:
    """确认积分账户归属用户存在。"""

    identity_repository = IdentityRepository(session)
    user = await identity_repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)
