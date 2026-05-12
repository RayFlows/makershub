# tests/test_organization_api.py
"""
组织与成员接口测试

本文件验证第一阶段成员资料闭环：登录用户可以读取并更新自己的成员资料，
部门列表需要登录访问，非法资料会被服务层拒绝。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.database.base import Base
from app.core.permissions.models import Permission, Role, RolePermission, UserRoleGrant
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import sync_registered_permissions
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.identity.models import (
    AuthSession,
    EmailPasswordAccount,
    EmailVerificationCode,
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
def organization_context(tmp_path: Path) -> Iterator[OrganizationTestContext]:
    """创建使用临时 SQLite 数据库的组织接口测试上下文。"""

    # 显式引用模型，确保 Base.metadata 在 create_all 前已经收集身份和组织表。
    _ = (
        AuthSession,
        AuditLog,
        EmailVerificationCode,
        EmailPasswordAccount,
        Permission,
        Role,
        RolePermission,
        User,
        UserRoleGrant,
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
                    Position(code="0", name="外部成员", status="active", sort_order=0, is_system=False),
                    Position(code="1", name="干事", status="active", sort_order=10, is_system=False),
                    Position(code="2", name="部长", status="active", sort_order=20, is_system=False),
                    Position(code="3", name="副会长", status="active", sort_order=30, is_system=False),
                    Position(code="4", name="会长", status="active", sort_order=40, is_system=False),
                    Position(code="5", name="指导老师", status="active", sort_order=50, is_system=False),
                    Position(code="998", name="管理员", status="active", sort_order=998, is_system=True),
                    Position(code="999", name="超级管理员", status="active", sort_order=999, is_system=True),
                ],
            )
            await sync_registered_permissions(session)
            await session.commit()

    asyncio.run(prepare_database())

    app = create_app()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    app.dependency_overrides[get_session] = override_get_session

    with TestClient(app) as client:
        yield OrganizationTestContext(client=client, session_factory=session_factory)

    app.dependency_overrides.clear()
    asyncio.run(engine.dispose())


@pytest.fixture
def organization_client(organization_context: OrganizationTestContext) -> TestClient:
    """保留旧测试使用的客户端 fixture。"""

    return organization_context.client


@dataclass(frozen=True)
class OrganizationTestContext:
    """组织接口测试上下文。"""

    client: TestClient
    session_factory: async_sessionmaker[AsyncSession]


def login_and_get_token(client: TestClient, *, openid: str = "dev_openid_org_1") -> str:
    """通过开发态微信登录获取访问令牌。"""

    response = client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": openid, "display_name": "组织测试用户"},
    )
    assert response.status_code == 200
    return response.json()["data"]["access_token"]


def login_and_get_identity(
    client: TestClient,
    *,
    openid: str,
    display_name: str = "组织测试用户",
) -> tuple[str, int]:
    """通过开发态微信登录获取访问令牌和用户 ID。"""

    response = client.post(
        "/api/v1/auth/wechat/login",
        json={"dev_openid": openid, "display_name": display_name},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    return data["access_token"], data["user"]["id"]


def grant_role_to_user(
    context: OrganizationTestContext,
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


def load_audit_actions(context: OrganizationTestContext) -> list[str]:
    """读取测试数据库中的审计动作。"""

    async def load() -> list[str]:
        async with context.session_factory() as session:
            result = await session.scalars(select(AuditLog.action).order_by(AuditLog.id))
            return list(result)

    return asyncio.run(load())


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


def test_member_admin_requires_permission(organization_client: TestClient) -> None:
    """普通登录用户不能进入后台成员管理接口。"""

    token = login_and_get_token(organization_client, openid="dev_openid_org_4")

    response = organization_client.get(
        "/api/v1/members",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "PERMISSION_DENIED"


def test_positions_include_external_member_and_hide_system_identity(
    organization_context: OrganizationTestContext,
) -> None:
    """后台可维护职务包含 0 基础身份，但不暴露 998/999。"""

    admin_token, admin_id = login_and_get_identity(
        organization_context.client,
        openid="dev_openid_org_positions_admin",
        display_name="组织管理员",
    )
    grant_role_to_user(organization_context, user_id=admin_id, role_code="organization_manager")

    response = organization_context.client.get(
        "/api/v1/positions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )

    assert response.status_code == 200
    codes = [item["code"] for item in response.json()["data"]]
    assert codes == ["0", "1", "2", "3", "4", "5"]


def test_member_admin_updates_profile_department_and_positions(
    organization_context: OrganizationTestContext,
) -> None:
    """拥有组织管理角色的用户可以维护成员基础资料、部门和职务。"""

    admin_token, admin_id = login_and_get_identity(
        organization_context.client,
        openid="dev_openid_org_admin",
        display_name="组织管理员",
    )
    _, target_id = login_and_get_identity(
        organization_context.client,
        openid="dev_openid_org_target",
        display_name="待维护成员",
    )
    grant_role_to_user(organization_context, user_id=admin_id, role_code="organization_manager")
    headers = {"Authorization": f"Bearer {admin_token}"}

    list_response = organization_context.client.get("/api/v1/members", headers=headers)
    assert list_response.status_code == 200
    assert list_response.json()["data"]["total"] == 2

    update_response = organization_context.client.patch(
        f"/api/v1/members/{target_id}",
        headers=headers,
        json={
            "display_name": "维护后的成员",
            "real_name": "王同学",
            "student_id": "20260088",
            "phone": "13800138001",
            "reason": "测试后台维护资料",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["data"]["user"]["display_name"] == "维护后的成员"
    assert update_response.json()["data"]["profile"]["student_id"] == "20260088"

    departments_response = organization_context.client.get(
        "/api/v1/departments",
        headers=headers,
    )
    project_department = next(item for item in departments_response.json()["data"] if item["code"] == "project")
    department_response = organization_context.client.patch(
        f"/api/v1/members/{target_id}/department",
        headers=headers,
        json={"department_id": project_department["id"], "reason": "加入项目部"},
    )
    assert department_response.status_code == 200
    assert department_response.json()["data"]["memberships"][0]["department"]["code"] == "project"

    positions_response = organization_context.client.patch(
        f"/api/v1/members/{target_id}/positions",
        headers=headers,
        json={"position_codes": ["2"], "department_id": project_department["id"], "reason": "任命部长"},
    )
    assert positions_response.status_code == 200
    position_data = positions_response.json()["data"]["positions"][0]
    assert position_data["position"]["code"] == "2"
    assert position_data["department"]["code"] == "project"

    actions = load_audit_actions(organization_context)
    assert "organization.member.update" in actions
    assert "organization.member.department.assign" in actions
    assert "organization.member.positions.replace" in actions


def test_member_positions_reject_system_identity(
    organization_context: OrganizationTestContext,
) -> None:
    """成员职务接口不能维护 998/999 系统底层身份。"""

    admin_token, admin_id = login_and_get_identity(
        organization_context.client,
        openid="dev_openid_org_admin_2",
        display_name="组织管理员",
    )
    _, target_id = login_and_get_identity(
        organization_context.client,
        openid="dev_openid_org_target_2",
        display_name="待维护成员",
    )
    grant_role_to_user(organization_context, user_id=admin_id, role_code="organization_manager")

    response = organization_context.client.patch(
        f"/api/v1/members/{target_id}/positions",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"position_codes": ["999"], "reason": "不能这样任命"},
    )

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SYSTEM_POSITION_FORBIDDEN"
