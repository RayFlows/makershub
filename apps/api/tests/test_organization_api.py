# tests/test_organization_api.py
"""
组织与成员接口测试

本文件验证第一阶段成员资料闭环：登录用户可以读取并更新自己的成员资料，
部门列表需要登录访问，非法资料会被服务层拒绝。
"""

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
from app.modules.identity.models import (
    AuthSession,
    EmailVerificationCode,
    LocalAccount,
    User,
    WechatAccount,
)
from app.modules.organization.models import (
    Department,
    DepartmentMembership,
    MemberProfile,
    Position,
    UserPosition,
)


@pytest.fixture
def organization_client(tmp_path: Path) -> Iterator[TestClient]:
    """创建使用临时 SQLite 数据库的组织接口测试客户端。"""

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集身份和组织表。
    _ = (
        AuthSession,
        EmailVerificationCode,
        LocalAccount,
        User,
        WechatAccount,
        Department,
        DepartmentMembership,
        MemberProfile,
        Position,
        UserPosition,
    )

    database_path = tmp_path / "organization.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            session.add_all(
                [
                    Department(code="publicity", name="宣传部", status="active", sort_order=10),
                    Department(code="infrastructure", name="基管部", status="active", sort_order=20),
                    Department(code="project", name="项目部", status="active", sort_order=30),
                    Department(code="operations", name="运维部", status="active", sort_order=40),
                ],
            )
            await session.commit()

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


def login_and_get_token(client: TestClient, *, openid: str = "dev_openid_org_1") -> str:
    """通过开发态微信登录获取访问令牌。"""

    response = client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": openid, "display_name": "组织测试用户"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def test_get_departments_requires_auth(organization_client: TestClient) -> None:
    response = organization_client.get("/api/v1/departments")

    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTH_HEADER_MISSING"


def test_get_my_profile_creates_empty_profile(organization_client: TestClient) -> None:
    token = login_and_get_token(organization_client)

    response = organization_client.get(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["profile"]["real_name"] is None
    assert body["data"]["profile"]["phone"] is None
    assert [item["name"] for item in body["data"]["departments"]] == ["宣传部", "基管部", "项目部", "运维部"]
    assert body["data"]["memberships"] == []


def test_update_my_profile_persists_fields(organization_client: TestClient) -> None:
    token = login_and_get_token(organization_client, openid="dev_openid_org_2")

    update_response = organization_client.patch(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "real_name": "测试同学",
            "student_id": "20260001",
            "phone": "13800138000",
            "college": "计算机学院",
            "major": "计算机科学与技术",
            "grade": "2026",
            "qq": "12345678",
            "bio": "喜欢开源硬件",
        },
    )

    assert update_response.status_code == 200
    profile = update_response.json()["data"]["profile"]
    assert profile["real_name"] == "测试同学"
    assert profile["phone"] == "13800138000"
    assert profile["qq"] == "12345678"

    get_response = organization_client.get(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert get_response.status_code == 200
    saved_profile = get_response.json()["data"]["profile"]
    assert saved_profile["student_id"] == "20260001"
    assert saved_profile["major"] == "计算机科学与技术"


def test_update_my_profile_rejects_invalid_phone(organization_client: TestClient) -> None:
    token = login_and_get_token(organization_client, openid="dev_openid_org_3")

    response = organization_client.patch(
        "/api/v1/me/profile",
        headers={"Authorization": f"Bearer {token}"},
        json={"phone": "123"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "MEMBER_PROFILE_PHONE_INVALID"
