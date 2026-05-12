# app/modules/identity/bootstrap/service.py
"""
唯一 999 初始化服务

本文件只处理系统第一个超级管理员的受控初始化。普通用户第一版必须先由小程序
微信登录建立用户主体，不能从网页端或后台端直接注册。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.modules.identity.repositories import IdentityRepository
from app.modules.identity.types import BootstrapSuperAdminResult
from app.modules.identity.utils import normalize_email, validate_initial_password
from app.modules.organization.models import Position, UserPosition


async def bootstrap_super_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str = "系统超级管理员",
) -> BootstrapSuperAdminResult:
    """初始化唯一 999 超级管理员。

    该流程只服务部署或灾备，不应暴露为普通业务接口。
    它会创建用户主体、邮箱密码账号，并授予全局 999 职务。
    """

    normalized_email = normalize_email(email)
    validate_initial_password(password)

    repository = IdentityRepository(session)
    existing_position = await repository.get_active_super_admin_position()
    existing_account = await repository.get_email_password_account_by_email(normalized_email)

    if existing_position is not None:
        raise AppError(
            "SUPER_ADMIN_ALREADY_EXISTS",
            "系统中已经存在有效的 999 超级管理员",
            status_code=409,
        )

    if existing_account is not None:
        raise AppError(
            "EMAIL_PASSWORD_ACCOUNT_ALREADY_EXISTS",
            "该邮箱已经绑定邮箱密码账号",
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

    user, email_password_account = await repository.create_email_password_user(
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
        email_password_account=email_password_account,
        user_position=user_position,
        created=True,
    )
