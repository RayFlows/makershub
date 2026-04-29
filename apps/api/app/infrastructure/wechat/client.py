# app/infrastructure/wechat/client.py
"""
微信小程序登录适配器

本文件只负责调用微信 code2session 接口，把临时 code 换成 openid/session_key。
它不负责创建用户，也不负责签发 MakersHub 自己的访问令牌。
"""

from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.core.config.settings import get_settings
from app.core.errors import AppError


@dataclass(frozen=True)
class WechatSession:
    """微信 code2session 返回的登录身份信息。"""

    openid: str
    unionid: str | None
    session_key: str | None


async def exchange_code_for_session(code: str) -> WechatSession:
    """
    调用微信 code2session 接口。

    Args:
        code: 小程序端 wx.login 返回的临时 code。

    Returns:
        微信登录身份信息。

    Raises:
        AppError: 微信配置缺失、网络失败或微信返回错误时抛出。
    """

    settings = get_settings()
    if not settings.wechat_app_id or not settings.wechat_app_secret:
        raise AppError(
            "WECHAT_CONFIG_MISSING",
            "微信小程序配置缺失",
            status_code=500,
        )

    params = {
        "appid": settings.wechat_app_id,
        "secret": settings.wechat_app_secret,
        "js_code": code,
        "grant_type": "authorization_code",
    }

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(settings.wechat_code2session_url, params=params)
            response.raise_for_status()
            payload = response.json()
    except httpx.HTTPError as exc:
        raise AppError("WECHAT_SERVICE_UNAVAILABLE", "微信登录服务暂时不可用", status_code=504) from exc

    errcode = payload.get("errcode")
    if errcode:
        errmsg = payload.get("errmsg", "unknown wechat error")
        raise AppError(
            "WECHAT_LOGIN_FAILED",
            f"微信登录失败: {errmsg}",
            status_code=502,
            details={"errcode": errcode},
        )

    openid = payload.get("openid")
    if not openid:
        raise AppError("WECHAT_OPENID_MISSING", "微信登录未返回 openid", status_code=502)

    return WechatSession(
        openid=openid,
        unionid=payload.get("unionid"),
        session_key=payload.get("session_key"),
    )
