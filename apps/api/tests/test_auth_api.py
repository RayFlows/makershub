# tests/test_auth_api.py
"""
身份认证接口测试

本文件验证微信登录、双令牌续签、邮箱绑定、首次登录、设置密码和密码登录闭环。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config.settings import get_settings
from app.core.database import get_session
from app.core.database.base import Base
from app.main import create_app
from app.modules.identity.models import (
    AuthSession,
    EmailPasswordAccount,
    EmailVerificationCode,
    User,
    WechatAccount,
)
from app.modules.organization.models import Position, UserPosition


@pytest.fixture
def auth_client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """创建使用临时 SQLite 数据库的认证接口测试客户端。"""

    # 认证接口测试需要稳定暴露 dev_code；本地 .env 即使切到真实 SMTP，也不能影响测试结果。
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "log")
    get_settings.cache_clear()

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集身份和组织表。
    _ = (AuthSession, EmailVerificationCode, EmailPasswordAccount, User, WechatAccount, Position, UserPosition)

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
    get_settings.cache_clear()


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
    refresh_token = body["data"]["refresh_token"]
    user_id = body["data"]["user"]["id"]
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["expires_in"] > 0
    assert body["data"]["expires_at"]
    assert refresh_token
    assert body["data"]["refresh_expires_at"]
    assert body["data"]["user"]["display_name"] == "开发用户"

    me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert me_response.status_code == 200
    me_body = me_response.json()
    assert me_body["success"] is True
    assert me_body["data"]["user"]["id"] == user_id
    assert me_body["data"]["user"]["email"] is None
    assert me_body["data"]["claims"]["channel"] == "wechat"
    assert me_body["data"]["permissions"]["codes"] == []
    assert me_body["data"]["permissions"]["is_super_admin"] is False


def test_refresh_token_rotates_refresh_token(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_refresh_1"},
    )
    refresh_token = login_response.json()["data"]["refresh_token"]

    refresh_response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )

    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    next_access_token = refresh_body["data"]["access_token"]
    next_refresh_token = refresh_body["data"]["refresh_token"]
    assert next_refresh_token != refresh_token

    old_refresh_response = auth_client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh_token},
    )
    assert old_refresh_response.status_code == 401
    assert old_refresh_response.json()["error"]["code"] == "INVALID_REFRESH_TOKEN"

    me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {next_access_token}"},
    )
    assert me_response.status_code == 200


def test_logout_revokes_access_session(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_logout_1"},
    )
    access_token = login_response.json()["data"]["access_token"]
    refresh_token = login_response.json()["data"]["refresh_token"]

    logout_response = auth_client.post(
        "/api/v1/auth/logout",
        json={"refresh_token": refresh_token},
    )

    assert logout_response.status_code == 200
    assert logout_response.json()["data"]["revoked"] is True

    me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 401
    assert me_response.json()["error"]["code"] == "AUTH_SESSION_REVOKED"


def test_send_email_code_and_bind_email(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_bind_email_1"},
    )
    access_token = login_response.json()["data"]["access_token"]

    send_response = auth_client.post(
        "/api/v1/auth/email/send-code",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "Ray@Example.COM", "purpose": "bind_email"},
    )

    assert send_response.status_code == 200
    send_body = send_response.json()
    assert send_body["data"]["email"] == "ray@example.com"
    assert send_body["data"]["purpose"] == "bind_email"
    assert send_body["data"]["delivery_mode"] == "log"
    code = send_body["data"]["dev_code"]
    assert len(code) == 6

    bind_response = auth_client.post(
        "/api/v1/auth/email/bind",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "ray@example.com", "code": code},
    )

    assert bind_response.status_code == 200
    bind_body = bind_response.json()
    assert bind_body["data"]["email"] == "ray@example.com"
    assert bind_body["data"]["created"] is True
    assert bind_body["data"]["password_required"] is True
    assert bind_body["data"]["user"]["email"] == "ray@example.com"

    me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {access_token}"},
    )
    assert me_response.status_code == 200
    assert me_response.json()["data"]["user"]["email"] == "ray@example.com"


def test_send_email_code_rate_limit(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_bind_email_2"},
    )
    access_token = login_response.json()["data"]["access_token"]

    first = auth_client.post(
        "/api/v1/auth/email/send-code",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "rate@example.com", "purpose": "bind_email"},
    )
    second = auth_client.post(
        "/api/v1/auth/email/send-code",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "rate@example.com", "purpose": "bind_email"},
    )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error"]["code"] == "EMAIL_CODE_TOO_FREQUENT"


def test_bind_email_rejects_invalid_code(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_bind_email_3"},
    )
    access_token = login_response.json()["data"]["access_token"]

    send_response = auth_client.post(
        "/api/v1/auth/email/send-code",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "wrong-code@example.com", "purpose": "bind_email"},
    )
    assert send_response.status_code == 200
    issued_code = send_response.json()["data"]["dev_code"]
    wrong_code = "000000" if issued_code != "000000" else "000001"

    bind_response = auth_client.post(
        "/api/v1/auth/email/bind",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "wrong-code@example.com", "code": wrong_code},
    )

    assert bind_response.status_code == 422
    assert bind_response.json()["error"]["code"] == "EMAIL_CODE_INVALID_OR_EXPIRED"


def test_first_login_sets_password_and_password_login(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_first_login_1"},
    )
    wechat_access_token = login_response.json()["data"]["access_token"]

    bind_code_response = auth_client.post(
        "/api/v1/auth/email/send-code",
        headers={"Authorization": f"Bearer {wechat_access_token}"},
        json={"email": "first-login@example.com", "purpose": "bind_email"},
    )
    bind_code = bind_code_response.json()["data"]["dev_code"]
    bind_response = auth_client.post(
        "/api/v1/auth/email/bind",
        headers={"Authorization": f"Bearer {wechat_access_token}"},
        json={"email": "first-login@example.com", "code": bind_code},
    )
    assert bind_response.status_code == 200

    first_login_code_response = auth_client.post(
        "/api/v1/auth/email/send-code",
        json={"email": "first-login@example.com", "purpose": "first_login"},
    )
    assert first_login_code_response.status_code == 200
    first_login_code = first_login_code_response.json()["data"]["dev_code"]

    first_login_response = auth_client.post(
        "/api/v1/auth/email/first-login",
        json={"email": "first-login@example.com", "code": first_login_code},
    )
    assert first_login_response.status_code == 200
    first_login_body = first_login_response.json()
    first_login_token = first_login_body["data"]["access_token"]
    assert first_login_body["data"]["password_required"] is True
    assert first_login_body["data"]["user"]["email"] == "first-login@example.com"

    first_login_me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {first_login_token}"},
    )
    assert first_login_me_response.status_code == 200
    assert first_login_me_response.json()["data"]["claims"]["channel"] == "email_code"

    set_password_response = auth_client.post(
        "/api/v1/auth/password/set",
        headers={"Authorization": f"Bearer {first_login_token}"},
        json={"password": "super-safe-password"},
    )
    assert set_password_response.status_code == 200
    assert set_password_response.json()["data"]["password_set"] is True

    repeat_first_login_code_response = auth_client.post(
        "/api/v1/auth/email/send-code",
        json={"email": "first-login@example.com", "purpose": "first_login"},
    )
    assert repeat_first_login_code_response.status_code == 409
    assert repeat_first_login_code_response.json()["error"]["code"] == "FIRST_LOGIN_NOT_REQUIRED"

    password_login_response = auth_client.post(
        "/api/v1/auth/password/login",
        json={"email": "first-login@example.com", "password": "super-safe-password"},
    )
    assert password_login_response.status_code == 200
    password_token = password_login_response.json()["data"]["access_token"]

    password_me_response = auth_client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {password_token}"},
    )
    assert password_me_response.status_code == 200
    assert password_me_response.json()["data"]["claims"]["channel"] == "password"


def test_password_login_rejects_unset_password(auth_client: TestClient) -> None:
    login_response = auth_client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": "dev_openid_first_login_2"},
    )
    access_token = login_response.json()["data"]["access_token"]

    send_response = auth_client.post(
        "/api/v1/auth/email/send-code",
        headers={"Authorization": f"Bearer {access_token}"},
        json={"email": "unset-password@example.com", "purpose": "bind_email"},
    )
    bind_response = auth_client.post(
        "/api/v1/auth/email/bind",
        headers={"Authorization": f"Bearer {access_token}"},
        json={
            "email": "unset-password@example.com",
            "code": send_response.json()["data"]["dev_code"],
        },
    )
    assert bind_response.status_code == 200

    password_login_response = auth_client.post(
        "/api/v1/auth/password/login",
        json={"email": "unset-password@example.com", "password": "super-safe-password"},
    )

    assert password_login_response.status_code == 403
    assert password_login_response.json()["error"]["code"] == "PASSWORD_NOT_SET"


def test_first_login_send_code_rejects_unbound_email(auth_client: TestClient) -> None:
    response = auth_client.post(
        "/api/v1/auth/email/send-code",
        json={"email": "unbound@example.com", "purpose": "first_login"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EMAIL_PASSWORD_ACCOUNT_NOT_FOUND"


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
