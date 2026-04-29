# app/interfaces/http/v1/auth/router.py
"""
身份认证 V1 路由

旧小程序使用 `/users/wx-login` 获取 token，并把 token 存在 `auth_token` 中。
新接口改为 `/api/v1/auth/wechat/login`，但继续使用标准 `Authorization: Bearer`
访问方式，以降低小程序后续适配成本。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.infrastructure.email import send_email_verification_code
from app.infrastructure.wechat import WechatSession, exchange_code_for_session
from app.interfaces.http.dependencies import CurrentUser, get_current_user
from app.interfaces.http.v1.auth.schemas import (
    BindEmailRequest,
    BindEmailResponse,
    EmailFirstLoginRequest,
    EmailFirstLoginResponse,
    LogoutRequest,
    PasswordLoginRequest,
    RefreshTokenRequest,
    SendEmailCodeRequest,
    SendEmailCodeResponse,
    SetPasswordRequest,
    SetPasswordResponse,
    TokenResponse,
    UserSummary,
    WechatLoginRequest,
)
from app.modules.identity.service import (
    AuthTokenPair,
    bind_email_with_code,
    complete_first_login_with_code,
    issue_auth_token_pair,
    issue_email_verification_code,
    login_local_account_with_password,
    login_wechat_identity,
    refresh_auth_token_pair,
    revoke_auth_token_pair,
    set_local_account_password,
)
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter(prefix="/auth")


def build_user_summary(user, *, local_account=None) -> UserSummary:
    """把用户 ORM 对象转换成接口层用户摘要。"""

    account = local_account
    if account is None and "local_account" not in inspect(user).unloaded:
        account = user.local_account

    return UserSummary(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        email=account.email if account is not None and account.status == "active" else None,
    )


def build_token_response(token_pair: AuthTokenPair) -> TokenResponse:
    """把服务层令牌对转换成 HTTP 响应模型。"""

    return TokenResponse(
        access_token=token_pair.access_token.token,
        refresh_token=token_pair.refresh_token,
        expires_in=token_pair.access_token.expires_in,
        expires_at=token_pair.access_token.expires_at,
        refresh_expires_at=token_pair.refresh_expires_at,
        user=build_user_summary(token_pair.user),
    )


def build_first_login_response(token_pair: AuthTokenPair) -> EmailFirstLoginResponse:
    """把首次邮箱验证码登录结果转换成 HTTP 响应模型。"""

    base = build_token_response(token_pair)
    return EmailFirstLoginResponse(**base.model_dump(), password_required=True)


def get_client_ip(request: Request) -> str | None:
    """提取客户端 IP。"""

    if request.client is None:
        return None
    return request.client.host


async def resolve_wechat_session(payload: WechatLoginRequest) -> WechatSession:
    """
    解析微信登录身份。

    本地开发允许传 dev_openid，避免没有微信开发者工具或真实 appid 时卡住；
    预发布和生产环境必须走真实 code2session。
    """

    settings = get_settings()
    if payload.dev_openid:
        if not settings.allow_dev_wechat_login:
            raise AppError("DEV_WECHAT_LOGIN_FORBIDDEN", "当前环境不允许开发态微信登录", status_code=403)
        return WechatSession(openid=payload.dev_openid, unionid=None, session_key=None)

    if not payload.code:
        raise AppError("WECHAT_CODE_REQUIRED", "缺少微信登录 code", status_code=422)

    return await exchange_code_for_session(payload.code)


@router.post("/wechat/login")
async def wechat_login(
    payload: WechatLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    小程序微信登录。

    成功后会创建或复用内部用户主体，并签发以内部 user_id 为 sub 的访问令牌。
    """

    wechat_session = await resolve_wechat_session(payload)
    result = await login_wechat_identity(
        session,
        openid=wechat_session.openid,
        unionid=wechat_session.unionid,
        session_key_hash=None,
        display_name=payload.display_name,
    )

    token_pair = await issue_auth_token_pair(
        session,
        user=result.user,
        channel="wechat",
        client_type="miniapp",
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    await session.commit()
    data = build_token_response(token_pair)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/refresh")
async def refresh_token(
    payload: RefreshTokenRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    使用 refresh token 续签令牌。

    refresh token 每次使用都会轮换，客户端必须保存本次响应里的新 refresh token。
    """

    token_pair = await refresh_auth_token_pair(
        session,
        refresh_token=payload.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    await session.commit()
    data = build_token_response(token_pair)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/logout")
async def logout(
    payload: LogoutRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """退出登录并撤销 refresh token 对应的登录会话。"""

    await revoke_auth_token_pair(
        session,
        refresh_token=payload.refresh_token,
        reason="logout",
    )
    await session.commit()
    return success_response({"revoked": True}, request_id=get_request_id(request))


@router.post("/email/send-code")
async def send_email_code(
    payload: SendEmailCodeRequest,
    request: Request,
    authorization: Annotated[str | None, Header(alias="Authorization")] = None,
    session: AsyncSession = Depends(get_session),
):
    """
    发送邮箱验证码。

    `bind_email` 需要当前登录用户；`first_login` 用于网页端首次登录，不要求已登录。
    """

    user_id = None
    if payload.purpose.strip().lower() == "bind_email":
        current = await get_current_user(authorization=authorization, session=session)
        user_id = current.user.id

    result, code = await issue_email_verification_code(
        session,
        email=payload.email,
        purpose=payload.purpose,
        user_id=user_id,
        request_ip=get_client_ip(request),
    )
    await send_email_verification_code(
        email=result.email,
        purpose=result.purpose,
        code=code,
        expires_minutes=get_settings().email_code_expire_minutes,
    )
    await session.commit()
    data = SendEmailCodeResponse(
        email=result.email,
        purpose=result.purpose,
        expires_at=result.expires_at,
        delivery_mode=result.delivery_mode,
        dev_code=result.dev_code,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/email/bind")
async def bind_email(
    payload: BindEmailRequest,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """使用邮箱验证码把邮箱绑定到当前用户主体。"""

    result = await bind_email_with_code(
        session,
        user_id=current.user.id,
        email=payload.email,
        code=payload.code,
    )
    await session.commit()
    data = BindEmailResponse(
        email=result.local_account.email,
        created=result.created,
        password_required=result.local_account.password_hash is None,
        user=build_user_summary(result.user, local_account=result.local_account),
    )
    return success_response(data.model_dump(), request_id=get_request_id(request))


@router.post("/email/first-login")
async def email_first_login(
    payload: EmailFirstLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    网页端首次邮箱验证码登录。

    该流程只接受已经绑定邮箱但尚未设置密码的本地账号，成功后客户端必须进入设置密码页。
    """

    result = await complete_first_login_with_code(
        session,
        email=payload.email,
        code=payload.code,
    )
    token_pair = await issue_auth_token_pair(
        session,
        user=result.user,
        channel="email_code",
        client_type="web",
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    await session.commit()
    data = build_first_login_response(token_pair)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/password/set")
async def set_password(
    payload: SetPasswordRequest,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """首次设置网页端本地账号密码。"""

    result = await set_local_account_password(
        session,
        user_id=current.user.id,
        password=payload.password,
    )
    await session.commit()
    data = SetPasswordResponse(
        password_set=result.password_set,
        user=build_user_summary(result.user, local_account=result.local_account),
    )
    return success_response(data.model_dump(), request_id=get_request_id(request))


@router.post("/password/login")
async def password_login(
    payload: PasswordLoginRequest,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """网页端邮箱密码登录。"""

    result = await login_local_account_with_password(
        session,
        email=payload.email,
        password=payload.password,
    )
    token_pair = await issue_auth_token_pair(
        session,
        user=result.user,
        channel="password",
        client_type="web",
        user_agent=request.headers.get("user-agent"),
        ip_address=get_client_ip(request),
    )
    await session.commit()
    data = build_token_response(token_pair)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/me")
async def get_me(
    request: Request,
    current: CurrentUser = Depends(get_current_user),
):
    """
    获取当前登录用户摘要。

    该接口用于前端启动时校验 token 是否仍然有效，并获取最小用户信息。
    """

    return success_response(
        {
            "user": build_user_summary(current.user).model_dump(),
            "claims": {
                "channel": current.claims.get("channel"),
            },
        },
        request_id=get_request_id(request),
    )
