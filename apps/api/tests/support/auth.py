# tests/support/auth.py
"""
测试认证与授权 helper

本文件只服务自动化测试：通过开发态微信登录拿测试 token，并在测试数据库中直接授予
预置角色。生产代码必须走真实接口和审计流程，不能复用这里的直授角色逻辑。
"""

from __future__ import annotations

import asyncio
from typing import Protocol

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.permissions.repository import PermissionRepository


class HasSessionFactory(Protocol):
    """拥有异步 Session 工厂的测试上下文协议。"""

    session_factory: async_sessionmaker[AsyncSession]


def login_wechat_identity(
    client: TestClient,
    *,
    openid: str,
    display_name: str = "接口测试用户",
) -> tuple[str, int]:
    """通过开发态微信登录获取访问令牌和用户 ID。"""

    response = client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": openid, "display_name": display_name},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return data["access_token"], data["user"]["id"]


def login_wechat_token(
    client: TestClient,
    *,
    openid: str,
    display_name: str = "接口测试用户",
) -> str:
    """通过开发态微信登录获取访问令牌。"""

    token, _ = login_wechat_identity(client, openid=openid, display_name=display_name)
    return token


def authorization_header(token: str) -> dict[str, str]:
    """构造 Bearer token 请求头。"""

    return {"Authorization": f"Bearer {token}"}


def grant_role_to_user(
    context: HasSessionFactory,
    *,
    user_id: int,
    role_code: str,
) -> None:
    """在测试数据库中直接授予预置角色。"""

    async def grant() -> None:
        async with context.session_factory() as session:
            repository = PermissionRepository(session)
            role = await repository.get_role_by_code(role_code)
            assert role is not None
            await repository.grant_role_to_user(user_id=user_id, role=role)
            await session.commit()

    asyncio.run(grant())
