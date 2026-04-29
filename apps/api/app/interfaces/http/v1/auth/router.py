# app/interfaces/http/v1/auth/router.py
"""
身份认证 V1 路由

旧小程序使用 `/users/wx-login` 获取 token，并把 token 存在 `auth_token` 中。
新接口改为 `/api/v1/auth/wechat/login`，但继续使用标准 `Authorization: Bearer`
访问方式，以降低小程序后续适配成本。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.database import get_session
from app.core.errors import AppError
from app.core.security import create_access_token
from app.infrastructure.wechat import WechatSession, exchange_code_for_session
from app.interfaces.http.dependencies import CurrentUser, get_current_user
from app.interfaces.http.v1.auth.schemas import TokenResponse, UserSummary, WechatLoginRequest
from app.modules.identity.service import login_wechat_identity
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter(prefix="/auth")


def build_user_summary(user) -> UserSummary:
    """把用户 ORM 对象转换成接口层用户摘要。"""

    return UserSummary(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
    )


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
    await session.commit()

    settings = get_settings()
    token = create_access_token(
        subject=result.user.id,
        extra_claims={"channel": "wechat"},
    )
    data = TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        user=build_user_summary(result.user),
    )
    return success_response(data.model_dump(), request_id=get_request_id(request))


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
