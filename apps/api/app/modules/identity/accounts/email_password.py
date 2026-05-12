# app/modules/identity/accounts/email_password.py
"""
邮箱密码账号服务

本文件负责微信用户绑定邮箱后形成邮箱密码账号、网页端首次邮箱验证码登录、
首次设置密码以及后续邮箱密码登录。普通用户不能通过本模块创建孤立网页账号。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.modules.identity.email_codes.service import consume_email_verification_code
from app.modules.identity.models import EmailPasswordAccount, User
from app.modules.identity.repositories import IdentityRepository
from app.modules.identity.types import BindEmailResult, EmailPasswordAccountAuthResult, PasswordSetResult
from app.modules.identity.utils import normalize_email, validate_password


async def bind_verified_email_to_user(
    session: AsyncSession,
    *,
    user_id: int,
    email: str,
) -> BindEmailResult:
    """把已验证邮箱绑定到现有用户主体。

    调用方必须先完成邮箱验证码校验。本函数只负责建立邮箱密码账号记录，
    并保持 password_hash 为空，等待网页端首次登录后强制设置密码。
    """

    normalized_email = normalize_email(email)
    repository = IdentityRepository(session)

    user = await repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)

    existing_account = await repository.get_email_password_account_by_email(normalized_email)
    if existing_account is not None:
        if existing_account.user_id == user_id:
            return BindEmailResult(user=user, email_password_account=existing_account, created=False)
        raise AppError("EMAIL_ALREADY_BOUND", "该邮箱已经绑定其他用户", status_code=409)

    user_account = await repository.get_email_password_account_by_user_id(user_id)
    if user_account is not None:
        raise AppError("EMAIL_PASSWORD_ACCOUNT_ALREADY_BOUND", "该用户已经绑定邮箱密码账号", status_code=409)

    account = await repository.create_pending_email_password_account(user=user, email=normalized_email)
    return BindEmailResult(user=user, email_password_account=account, created=True)


async def bind_email_with_code(
    session: AsyncSession,
    *,
    user_id: int,
    email: str,
    code: str,
) -> BindEmailResult:
    """使用邮箱验证码绑定邮箱密码登录入口。"""

    await consume_email_verification_code(
        session,
        email=email,
        purpose="bind_email",
        code=code,
        user_id=user_id,
    )
    return await bind_verified_email_to_user(session, user_id=user_id, email=email)


async def complete_first_login_with_code(
    session: AsyncSession,
    *,
    email: str,
    code: str,
) -> EmailPasswordAccountAuthResult:
    """使用邮箱验证码完成网页端首次登录校验。

    只有已经通过小程序绑定邮箱、但尚未设置密码的邮箱密码账号可以进入该流程。
    接口层会在本函数成功后签发登录令牌，并要求网页端立即进入设置密码页。
    """

    normalized_email = normalize_email(email)
    repository = IdentityRepository(session)
    account = await repository.get_email_password_account_by_email(normalized_email)
    if account is None or account.status != "active":
        raise AppError("EMAIL_PASSWORD_ACCOUNT_NOT_FOUND", "该邮箱尚未绑定账号", status_code=404)
    if account.password_hash is not None:
        raise AppError("FIRST_LOGIN_NOT_REQUIRED", "该邮箱已设置密码，请使用密码登录", status_code=409)

    await consume_email_verification_code(
        session,
        email=normalized_email,
        purpose="first_login",
        code=code,
        user_id=account.user_id,
    )
    user = await load_active_user_for_email_password_account(repository, account)
    await repository.mark_user_login(user)
    return EmailPasswordAccountAuthResult(user=user, email_password_account=account, password_required=True)


async def set_email_password_account_password(
    session: AsyncSession,
    *,
    user_id: int,
    password: str,
) -> PasswordSetResult:
    """为当前登录用户首次设置邮箱密码登录密码。"""

    validate_password(password)
    repository = IdentityRepository(session)
    account = await repository.get_email_password_account_by_user_id(user_id)
    if account is None:
        raise AppError("EMAIL_PASSWORD_ACCOUNT_NOT_BOUND", "当前用户尚未绑定邮箱账号", status_code=409)
    if account.status != "active":
        raise AppError("EMAIL_PASSWORD_ACCOUNT_DISABLED", "邮箱密码账号状态不可用", status_code=403)
    if account.password_hash is not None:
        raise AppError("PASSWORD_ALREADY_SET", "该账号已经设置过密码", status_code=409)

    user = await load_active_user_for_email_password_account(repository, account)
    await repository.set_email_password_account_password(account, password_hash=hash_password(password))
    return PasswordSetResult(user=user, email_password_account=account, password_set=True)


async def login_email_password_account_with_password(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> EmailPasswordAccountAuthResult:
    """使用邮箱和密码登录邮箱密码账号。"""

    normalized_email = normalize_email(email)
    repository = IdentityRepository(session)
    account = await repository.get_email_password_account_by_email(normalized_email)
    if account is None or account.status != "active":
        raise AppError("INVALID_EMAIL_OR_PASSWORD", "邮箱或密码错误", status_code=401)
    if account.password_hash is None:
        raise AppError("PASSWORD_NOT_SET", "该邮箱尚未设置密码，请先完成首次登录", status_code=403)
    if not verify_password(password, account.password_hash):
        raise AppError("INVALID_EMAIL_OR_PASSWORD", "邮箱或密码错误", status_code=401)

    user = await load_active_user_for_email_password_account(repository, account)
    await repository.mark_user_login(user)
    return EmailPasswordAccountAuthResult(user=user, email_password_account=account, password_required=False)


async def load_active_user_for_email_password_account(
    repository: IdentityRepository,
    account: EmailPasswordAccount,
) -> User:
    """读取邮箱密码账号所属的可用用户主体。"""

    user = await repository.get_user_by_id(account.user_id)
    if user is None:
        raise AppError("AUTH_USER_NOT_FOUND", "登录用户不存在", status_code=401)
    if user.status != "active":
        raise AppError("AUTH_USER_DISABLED", "用户状态不可用", status_code=403)
    return user
