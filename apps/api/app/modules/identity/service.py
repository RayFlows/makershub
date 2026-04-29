# app/modules/identity/service.py
"""
身份域业务服务

本模块承接 requirements-checklist.md 中确认的登录链路：
普通用户先通过小程序微信登录创建用户主体，再绑定邮箱，最后网页端首次登录设置密码。
第一个 999 是唯一例外，可以由受控运维命令直接创建本地账号。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password
from app.modules.identity.models import LocalAccount, User, WechatAccount
from app.modules.identity.repository import IdentityRepository
from app.modules.organization.models import Position, UserPosition


@dataclass(frozen=True)
class BootstrapSuperAdminResult:
    """初始化 999 的返回结果。"""

    user: User
    local_account: LocalAccount
    user_position: UserPosition
    created: bool


@dataclass(frozen=True)
class WechatLoginResult:
    """微信登录的返回结果。"""

    user: User
    wechat_account: WechatAccount
    created: bool


@dataclass(frozen=True)
class BindEmailResult:
    """邮箱绑定的返回结果。"""

    user: User
    local_account: LocalAccount
    created: bool


async def bootstrap_super_admin(
    session: AsyncSession,
    *,
    email: str,
    password: str,
    display_name: str = "系统超级管理员",
) -> BootstrapSuperAdminResult:
    """初始化唯一 999 超级管理员。

    该流程只服务部署或灾备，不应暴露为普通业务接口。
    它会创建用户主体、本地账号，并授予全局 999 职务。
    """

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


async def login_wechat_identity(
    session: AsyncSession,
    *,
    openid: str,
    unionid: str | None = None,
    session_key_hash: str | None = None,
    display_name: str | None = None,
) -> WechatLoginResult:
    """处理小程序微信登录。

    - 已存在 openid：复用同一个用户主体，并刷新登录时间；
    - 首次出现 openid：创建用户主体和微信凭证；
    - unionid 暂时可空，但如果传入，必须和已有绑定关系一致。
    """

    normalized_openid = normalize_wechat_identifier(openid, field_name="openid")
    normalized_unionid = normalize_wechat_identifier(unionid, field_name="unionid") if unionid else None

    repository = IdentityRepository(session)
    account = await repository.get_wechat_account_by_openid(normalized_openid)

    if account is not None:
        if account.status != "active":
            raise AppError("WECHAT_ACCOUNT_DISABLED", "微信账号已被禁用", status_code=403)
        # 同一个 openid 后续拿到的 unionid 不能变化，否则说明微信身份映射异常。
        if account.unionid and normalized_unionid and account.unionid != normalized_unionid:
            raise AppError("WECHAT_UNIONID_CONFLICT", "微信 unionid 与已有账号不一致", status_code=409)
        user = await repository.mark_wechat_login(
            account,
            unionid=normalized_unionid,
            session_key_hash=session_key_hash,
        )
        return WechatLoginResult(user=user, wechat_account=account, created=False)

    if normalized_unionid:
        # 避免把新的 openid 错绑到已经属于另一个用户主体的 unionid 上。
        existing_union_account = await repository.get_wechat_account_by_unionid(normalized_unionid)
        if existing_union_account is not None:
            raise AppError("WECHAT_UNIONID_ALREADY_BOUND", "微信 unionid 已经绑定其他账号", status_code=409)

    user, account = await repository.create_wechat_user(
        openid=normalized_openid,
        unionid=normalized_unionid,
        session_key_hash=session_key_hash,
        display_name=display_name or "微信用户",
    )
    return WechatLoginResult(user=user, wechat_account=account, created=True)


async def bind_verified_email_to_user(
    session: AsyncSession,
    *,
    user_id: int,
    email: str,
) -> BindEmailResult:
    """把已验证邮箱绑定到现有用户主体。

    调用方必须先完成邮箱验证码校验。本函数只负责建立本地账号记录，
    并保持 password_hash 为空，等待网页端首次登录后强制设置密码。
    """

    normalized_email = normalize_email(email)
    repository = IdentityRepository(session)

    user = await repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)

    existing_account = await repository.get_local_account_by_email(normalized_email)
    if existing_account is not None:
        if existing_account.user_id == user_id:
            return BindEmailResult(user=user, local_account=existing_account, created=False)
        raise AppError("EMAIL_ALREADY_BOUND", "该邮箱已经绑定其他用户", status_code=409)

    user_account = await repository.get_local_account_by_user_id(user_id)
    if user_account is not None:
        raise AppError("LOCAL_ACCOUNT_ALREADY_BOUND", "该用户已经绑定本地账号", status_code=409)

    account = await repository.create_pending_local_account(user=user, email=normalized_email)
    return BindEmailResult(user=user, local_account=account, created=True)


def normalize_email(email: str) -> str:
    """规范化邮箱登录名。"""

    normalized = email.strip().lower()
    if "@" not in normalized:
        raise AppError("INVALID_EMAIL", "邮箱格式不合法", status_code=422)
    return normalized


def normalize_wechat_identifier(value: str, *, field_name: str) -> str:
    """规范化微信返回的 openid/unionid。"""

    normalized = value.strip()
    if not normalized:
        raise AppError("INVALID_WECHAT_IDENTIFIER", f"{field_name} 不能为空", status_code=422)
    return normalized


def validate_initial_password(password: str) -> None:
    """校验初始化 999 使用的本地账号密码。"""

    if len(password) < 8:
        raise AppError("PASSWORD_TOO_SHORT", "密码至少需要 8 位", status_code=422)
