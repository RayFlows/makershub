from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.database.base import Base
from app.main import create_app
from app.modules.identity.models import EmailVerificationCode, LocalAccount, User, WechatAccount
from app.modules.organization.models import Position, UserPosition


@pytest.fixture
def auth_client(tmp_path: Path) -> Iterator[TestClient]:
    """创建使用临时 SQLite 数据库的认证接口测试客户端。"""

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集身份和组织表。
    _ = (EmailVerificationCode, LocalAccount, User, WechatAccount, Position, UserPosition)

    database_path = tmp_path / "auth.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    asyncio.run(prepare_database())

    app = create_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield client

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


def test_wechat_dev_login_returns_token_and_me(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={
            "dev_openid": "dev_openid_auth_1",
            "display_name": "开发用户",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    token = body["data"]["access_token"]
    user_id = body["data"]["user"]["id"]
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["expires_in"] > 0
    assert body["data"]["expires_at"]
    assert body["data"]["user"]["display_name"] == "开发用户"

    me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["success"] is True
    assert me_body["data"]["user"]["id"] == user_id
    assert me_body["data"]["claims"]["channel"] == "wechat"


def test_wechat_dev_login_reuses_same_user(auth_client: TestClient) -> None:
    first = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_auth_2"},
    )
    second = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_auth_2"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json()["data"]["user"]["id"] == second.json()["data"]["user"]["id"]


def test_get_me_requires_authorization_header(auth_client: TestClient) -> None:
    response = auth_client.get("/api/v1/auth/me")

    assert response.status_code == 401
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "AUTH_HEADER_MISSING"
