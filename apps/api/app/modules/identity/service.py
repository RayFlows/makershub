# app/modules/identity/service.py
"""
身份域业务服务

本模块承接 requirements-checklist.md 中确认的登录链路：
普通用户先通过小程序微信登录创建用户主体，再绑定邮箱，最后网页端首次登录设置密码。
第一个 999 是唯一例外，可以由受控运维命令直接创建本地账号。
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.core.security import AccessToken, hash_password, issue_access_token, verify_password
from app.modules.identity.models import (
    AuthSession,
    EmailVerificationCode,
    LocalAccount,
    User,
    WechatAccount,
)
from app.modules.identity.repository import IdentityRepository
from app.modules.organization.models import Position, UserPosition
from app.shared.time import utc_now


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


@dataclass(frozen=True)
class LocalAccountAuthResult:
    """本地账号登录或首次登录校验结果。"""

    user: User
    local_account: LocalAccount
    password_required: bool


@dataclass(frozen=True)
class PasswordSetResult:
    """设置密码结果。"""

    user: User
    local_account: LocalAccount
    password_set: bool


@dataclass(frozen=True)
class AuthTokenPair:
    """登录令牌对。"""

    user: User
    auth_session: AuthSession
    access_token: AccessToken
    refresh_token: str
    refresh_expires_at: datetime


@dataclass(frozen=True)
class EmailVerificationIssueResult:
    """邮箱验证码签发结果。"""

    email: str
    purpose: str
    expires_at: datetime
    delivery_mode: str
    dev_code: str | None


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


async def issue_email_verification_code(
    session: AsyncSession,
    *,
    email: str,
    purpose: str,
    user_id: int | None,
    request_ip: str | None = None,
) -> tuple[EmailVerificationIssueResult, str]:
    """生成并保存邮箱验证码。

    本函数只负责验证码规则和落库，真正发送由 infrastructure/email 完成。
    """

    normalized_email = normalize_email(email)
    normalized_purpose = normalize_email_code_purpose(purpose)
    settings = get_settings()
    now = utc_now()
    repository = IdentityRepository(session)

    if normalized_purpose == "bind_email":
        if user_id is None:
            raise AppError("AUTH_REQUIRED_FOR_EMAIL_BIND", "绑定邮箱需要先登录", status_code=401)
        existing_account = await repository.get_local_account_by_email(normalized_email)
        if existing_account is not None and existing_account.user_id != user_id:
            raise AppError("EMAIL_ALREADY_BOUND", "该邮箱已经绑定其他用户", status_code=409)
        code_user_id = user_id
    elif normalized_purpose == "first_login":
        existing_account = await repository.get_local_account_by_email(normalized_email)
        if existing_account is None or existing_account.status != "active":
            raise AppError("LOCAL_ACCOUNT_NOT_FOUND", "该邮箱尚未绑定账号", status_code=404)
        if existing_account.password_hash is not None:
            raise AppError("FIRST_LOGIN_NOT_REQUIRED", "该邮箱已设置密码，请使用密码登录", status_code=409)
        code_user_id = existing_account.user_id
    else:
        code_user_id = user_id

    latest = await repository.get_latest_email_verification_code(
        email=normalized_email,
        purpose=normalized_purpose,
        user_id=code_user_id,
    )
    if latest is not None:
        latest_created_at = ensure_aware_datetime(latest.created_at)
        elapsed_seconds = (now - latest_created_at).total_seconds()
        if elapsed_seconds < settings.email_code_resend_interval_seconds:
            retry_after = max(1, int(settings.email_code_resend_interval_seconds - elapsed_seconds))
            raise AppError(
                "EMAIL_CODE_TOO_FREQUENT",
                "验证码请求过于频繁",
                status_code=429,
                details={"retry_after_seconds": retry_after},
            )

    sent_count = await repository.count_email_verification_codes_since(
        email=normalized_email,
        purpose=normalized_purpose,
        since=now - timedelta(hours=1),
    )
    if sent_count >= settings.email_code_hourly_limit:
        raise AppError(
            "EMAIL_CODE_HOURLY_LIMIT_EXCEEDED",
            "该邮箱验证码发送次数已达上限",
            status_code=429,
        )

    code = generate_email_verification_code()
    expires_at = now + timedelta(minutes=settings.email_code_expire_minutes)
    await repository.create_email_verification_code(
        email=normalized_email,
        purpose=normalized_purpose,
        code_hash=hash_email_verification_code(
            email=normalized_email,
            purpose=normalized_purpose,
            code=code,
        ),
        expires_at=expires_at,
        request_ip=trim_optional_text(request_ip, max_length=64),
        user_id=code_user_id,
    )
    result = EmailVerificationIssueResult(
        email=normalized_email,
        purpose=normalized_purpose,
        expires_at=expires_at,
        delivery_mode=settings.email_delivery_mode.lower(),
        dev_code=code if should_expose_dev_email_code() else None,
    )
    return result, code


async def consume_email_verification_code(
    session: AsyncSession,
    *,
    email: str,
    purpose: str,
    code: str,
    user_id: int | None,
) -> EmailVerificationCode:
    """校验并消费邮箱验证码。"""

    normalized_email = normalize_email(email)
    normalized_purpose = normalize_email_code_purpose(purpose)
    normalized_code = normalize_email_verification_code(code)
    repository = IdentityRepository(session)
    record = await repository.get_usable_email_verification_code(
        email=normalized_email,
        purpose=normalized_purpose,
        code_hash=hash_email_verification_code(
            email=normalized_email,
            purpose=normalized_purpose,
            code=normalized_code,
        ),
        user_id=user_id,
        now=utc_now(),
    )
    if record is None:
        raise AppError("EMAIL_CODE_INVALID_OR_EXPIRED", "验证码无效或已过期", status_code=422)

    await repository.consume_email_verification_code(record)
    return record


async def bind_email_with_code(
    session: AsyncSession,
    *,
    user_id: int,
    email: str,
    code: str,
) -> BindEmailResult:
    """使用邮箱验证码绑定本地账号入口。"""

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
) -> LocalAccountAuthResult:
    """使用邮箱验证码完成网页端首次登录校验。

    只有已经通过小程序绑定邮箱、但尚未设置密码的本地账号可以进入该流程。
    接口层会在本函数成功后签发登录令牌，并要求网页端立即进入设置密码页。
    """

    normalized_email = normalize_email(email)
    repository = IdentityRepository(session)
    account = await repository.get_local_account_by_email(normalized_email)
    if account is None or account.status != "active":
        raise AppError("LOCAL_ACCOUNT_NOT_FOUND", "该邮箱尚未绑定账号", status_code=404)
    if account.password_hash is not None:
        raise AppError("FIRST_LOGIN_NOT_REQUIRED", "该邮箱已设置密码，请使用密码登录", status_code=409)

    await consume_email_verification_code(
        session,
        email=normalized_email,
        purpose="first_login",
        code=code,
        user_id=account.user_id,
    )
    user = await load_active_user_for_local_account(repository, account)
    await repository.mark_user_login(user)
    return LocalAccountAuthResult(user=user, local_account=account, password_required=True)


async def set_local_account_password(
    session: AsyncSession,
    *,
    user_id: int,
    password: str,
) -> PasswordSetResult:
    """为当前登录用户首次设置本地账号密码。"""

    validate_password(password)
    repository = IdentityRepository(session)
    account = await repository.get_local_account_by_user_id(user_id)
    if account is None:
        raise AppError("LOCAL_ACCOUNT_NOT_BOUND", "当前用户尚未绑定邮箱账号", status_code=409)
    if account.status != "active":
        raise AppError("LOCAL_ACCOUNT_DISABLED", "本地账号状态不可用", status_code=403)
    if account.password_hash is not None:
        raise AppError("PASSWORD_ALREADY_SET", "该账号已经设置过密码", status_code=409)

    user = await load_active_user_for_local_account(repository, account)
    await repository.set_local_account_password(account, password_hash=hash_password(password))
    return PasswordSetResult(user=user, local_account=account, password_set=True)


async def login_local_account_with_password(
    session: AsyncSession,
    *,
    email: str,
    password: str,
) -> LocalAccountAuthResult:
    """使用邮箱和密码登录本地账号。"""

    normalized_email = normalize_email(email)
    repository = IdentityRepository(session)
    account = await repository.get_local_account_by_email(normalized_email)
    if account is None or account.status != "active":
        raise AppError("INVALID_EMAIL_OR_PASSWORD", "邮箱或密码错误", status_code=401)
    if account.password_hash is None:
        raise AppError("PASSWORD_NOT_SET", "该邮箱尚未设置密码，请先完成首次登录", status_code=403)
    if not verify_password(password, account.password_hash):
        raise AppError("INVALID_EMAIL_OR_PASSWORD", "邮箱或密码错误", status_code=401)

    user = await load_active_user_for_local_account(repository, account)
    await repository.mark_user_login(user)
    return LocalAccountAuthResult(user=user, local_account=account, password_required=False)


async def issue_auth_token_pair(
    session: AsyncSession,
    *,
    user: User,
    channel: str,
    client_type: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthTokenPair:
    """签发 access token + refresh token。

    access token 是短期 JWT，负责接口访问；refresh token 是长期随机凭证，
    只以哈希形式保存到 auth_sessions，用于续签和撤销。
    """

    normalized_channel = normalize_session_label(channel, field_name="channel")
    normalized_client_type = normalize_session_label(client_type, field_name="client_type")
    settings = get_settings()
    refresh_token = generate_refresh_token()
    refresh_expires_at = utc_now() + timedelta(days=settings.refresh_token_expire_days)

    repository = IdentityRepository(session)
    auth_session = await repository.create_auth_session(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(refresh_token),
        channel=normalized_channel,
        client_type=normalized_client_type,
        expires_at=refresh_expires_at,
        user_agent=trim_optional_text(user_agent, max_length=512),
        ip_address=trim_optional_text(ip_address, max_length=64),
    )
    access_token = issue_access_token(
        subject=user.id,
        extra_claims={
            "channel": normalized_channel,
            "sid": auth_session.id,
        },
    )
    return AuthTokenPair(
        user=user,
        auth_session=auth_session,
        access_token=access_token,
        refresh_token=refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


async def refresh_auth_token_pair(
    session: AsyncSession,
    *,
    refresh_token: str,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> AuthTokenPair:
    """使用 refresh token 续签令牌对。

    每次续签都会轮换 refresh token，旧 refresh token 立即失效。
    这样即使旧 token 泄露，也能在下一次合法续签后降低继续使用的窗口。
    """

    repository = IdentityRepository(session)
    auth_session = await repository.get_auth_session_by_refresh_hash(hash_refresh_token(refresh_token))
    if auth_session is None:
        raise AppError("INVALID_REFRESH_TOKEN", "刷新令牌无效", status_code=401)

    ensure_auth_session_usable(auth_session)
    user = await repository.get_user_by_id(auth_session.user_id)
    if user is None:
        raise AppError("AUTH_USER_NOT_FOUND", "登录用户不存在", status_code=401)
    if user.status != "active":
        raise AppError("AUTH_USER_DISABLED", "用户状态不可用", status_code=403)

    settings = get_settings()
    next_refresh_token = generate_refresh_token()
    refresh_expires_at = utc_now() + timedelta(days=settings.refresh_token_expire_days)
    await repository.rotate_auth_session(
        auth_session,
        refresh_token_hash=hash_refresh_token(next_refresh_token),
        expires_at=refresh_expires_at,
        user_agent=trim_optional_text(user_agent, max_length=512),
        ip_address=trim_optional_text(ip_address, max_length=64),
    )
    access_token = issue_access_token(
        subject=user.id,
        extra_claims={
            "channel": auth_session.channel,
            "sid": auth_session.id,
        },
    )
    return AuthTokenPair(
        user=user,
        auth_session=auth_session,
        access_token=access_token,
        refresh_token=next_refresh_token,
        refresh_expires_at=refresh_expires_at,
    )


async def revoke_auth_token_pair(
    session: AsyncSession,
    *,
    refresh_token: str,
    reason: str = "logout",
) -> AuthSession:
    """撤销 refresh token 对应的登录会话。"""

    repository = IdentityRepository(session)
    auth_session = await repository.get_auth_session_by_refresh_hash(hash_refresh_token(refresh_token))
    if auth_session is None:
        raise AppError("INVALID_REFRESH_TOKEN", "刷新令牌无效", status_code=401)

    if auth_session.status == "revoked":
        return auth_session

    await repository.revoke_auth_session(auth_session, reason=reason)
    return auth_session


async def validate_auth_session(
    session: AsyncSession,
    *,
    auth_session_id: int,
) -> AuthSession:
    """校验 access token 中携带的会话是否仍然有效。"""

    repository = IdentityRepository(session)
    auth_session = await repository.get_auth_session_by_id(auth_session_id)
    if auth_session is None:
        raise AppError("AUTH_SESSION_NOT_FOUND", "登录会话不存在", status_code=401)
    ensure_auth_session_usable(auth_session)
    return auth_session


def normalize_email(email: str) -> str:
    """规范化邮箱登录名。"""

    normalized = email.strip().lower()
    if "@" not in normalized or len(normalized) > 255:
        raise AppError("INVALID_EMAIL", "邮箱格式不合法", status_code=422)
    return normalized


def normalize_email_code_purpose(purpose: str) -> str:
    """规范化邮箱验证码用途。"""

    normalized = purpose.strip().lower()
    if normalized not in {"bind_email", "first_login"}:
        raise AppError("EMAIL_CODE_PURPOSE_UNSUPPORTED", "当前验证码用途暂未支持", status_code=422)
    return normalized


def normalize_email_verification_code(code: str) -> str:
    """规范化用户提交的邮箱验证码。"""

    normalized = code.strip()
    if len(normalized) != 6 or not normalized.isdigit():
        raise AppError("EMAIL_CODE_FORMAT_INVALID", "验证码格式不合法", status_code=422)
    return normalized


def normalize_wechat_identifier(value: str, *, field_name: str) -> str:
    """规范化微信返回的 openid/unionid。"""

    normalized = value.strip()
    if not normalized:
        raise AppError("INVALID_WECHAT_IDENTIFIER", f"{field_name} 不能为空", status_code=422)
    return normalized


def validate_initial_password(password: str) -> None:
    """校验初始化 999 使用的本地账号密码。"""

    validate_password(password)


def validate_password(password: str) -> None:
    """校验本地账号密码复杂度底线。"""

    if len(password) < 8:
        raise AppError("PASSWORD_TOO_SHORT", "密码至少需要 8 位", status_code=422)


def generate_refresh_token() -> str:
    """生成高熵 refresh token。"""

    return secrets.token_urlsafe(48)


def generate_email_verification_code() -> str:
    """生成 6 位数字邮箱验证码。"""

    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_verification_code(*, email: str, purpose: str, code: str) -> str:
    """计算邮箱验证码哈希。"""

    settings = get_settings()
    message = f"{purpose}:{email}:{code}".encode()
    return hmac.new(settings.jwt_secret_key.encode("utf-8"), message, hashlib.sha256).hexdigest()


def should_expose_dev_email_code() -> bool:
    """本地和测试环境是否允许在响应中暴露验证码。"""

    settings = get_settings()
    return settings.app_env in {"local", "test", "development"} and settings.email_delivery_mode.lower() == "log"


def hash_refresh_token(refresh_token: str) -> str:
    """计算 refresh token 哈希，避免数据库保存明文长期凭证。"""

    normalized = refresh_token.strip()
    if not normalized:
        raise AppError("REFRESH_TOKEN_REQUIRED", "缺少刷新令牌", status_code=422)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def normalize_session_label(value: str, *, field_name: str) -> str:
    """规范化会话来源标签。"""

    normalized = value.strip().lower()
    if not normalized:
        raise AppError("INVALID_AUTH_SESSION_LABEL", f"{field_name} 不能为空", status_code=422)
    return normalized


def trim_optional_text(value: str | None, *, max_length: int) -> str | None:
    """裁剪可选文本，避免请求头等客户端输入超过数据库字段长度。"""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    return normalized[:max_length]


def ensure_auth_session_usable(auth_session: AuthSession) -> None:
    """确认登录会话仍处于可使用状态。"""

    if auth_session.status == "revoked" or auth_session.revoked_at is not None:
        raise AppError("AUTH_SESSION_REVOKED", "登录会话已失效", status_code=401)
    if auth_session.status != "active":
        raise AppError("AUTH_SESSION_DISABLED", "登录会话不可用", status_code=401)
    if ensure_aware_datetime(auth_session.expires_at) <= utc_now():
        raise AppError("REFRESH_TOKEN_EXPIRED", "刷新令牌已过期", status_code=401)


def ensure_aware_datetime(value: datetime) -> datetime:
    """确保数据库时间可以和 UTC 当前时间比较。"""

    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value


async def load_active_user_for_local_account(
    repository: IdentityRepository,
    account: LocalAccount,
) -> User:
    """读取本地账号所属的可用用户主体。"""

    user = await repository.get_user_by_id(account.user_id)
    if user is None:
        raise AppError("AUTH_USER_NOT_FOUND", "登录用户不存在", status_code=401)
    if user.status != "active":
        raise AppError("AUTH_USER_DISABLED", "用户状态不可用", status_code=403)
    return user
