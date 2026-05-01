# tests/test_permissions.py
"""
权限基础设施测试

当前只验证权限点注册表的基础行为。完整授权、角色和作用域规则会在权限系统
数据库表落地后继续补充测试。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.database.base import Base
from app.core.permissions import (
    PermissionPoint,
    PermissionRegistry,
    PermissionRiskLevel,
    permission_registry,
)
from app.core.permissions.models import Permission, Role
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import (
    check_user_permission,
    get_user_permission_summary,
    sync_registered_permissions,
)
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.identity.models import AuthSession, EmailVerificationCode, LocalAccount, User, WechatAccount
from app.modules.organization.models import Position, UserPosition


def test_core_permission_registry_contains_required_points() -> None:
    """核心权限点应该在应用启动前完成注册。"""

    codes = {point.code for point in permission_registry.list()}

    assert "system.admin.access" in codes
    assert "system.audit.view" in codes
    assert "organization.member.manage" in codes
    assert "organization.department.manage" in codes
    assert "organization.position.manage" in codes
    assert "system.operator.manage" in codes
    assert "system.super_admin.recover" in codes


def test_permission_registry_rejects_duplicate_code() -> None:
    """重复权限点 code 应该直接报错，避免菜单和接口鉴权歧义。"""

    registry = PermissionRegistry()
    point = PermissionPoint(
        code="example.manage",
        name="示例权限",
        module="example",
        description="测试重复注册",
        risk_level=PermissionRiskLevel.LOW,
    )

    registry.register(point)
    with pytest.raises(ValueError, match="权限点重复注册"):
        registry.register(point)


@pytest.mark.asyncio
async def test_sync_registered_permissions_creates_roles_and_permissions() -> None:
    """权限注册表应该可以幂等同步到数据库。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await sync_registered_permissions(session)
        second_result = await sync_registered_permissions(session)
        await session.commit()

    async with session_factory() as session:
        permissions = list(await session.scalars(select(Permission)))
        roles = list(await session.scalars(select(Role)))

    assert result.permission_count == len(permission_registry.list())
    assert second_result.permission_count == result.permission_count
    assert result.role_count >= 4
    assert {item.code for item in permissions} >= {"system.admin.access", "files.manage"}
    assert {item.code for item in roles} >= {"system_super_admin", "organization_manager"}

    await engine.dispose()


@pytest.mark.asyncio
async def test_role_grant_controls_permission_codes() -> None:
    """普通用户只获得被授予角色中的权限点。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await sync_registered_permissions(session)
        user = User(display_name="权限测试用户", status="active")
        session.add(user)
        await session.flush()

        repository = PermissionRepository(session)
        role = await repository.get_role_by_code("organization_manager")
        assert role is not None
        await repository.grant_role_to_user(user_id=user.id, role=role)
        await session.commit()
        user_id = user.id

    async with session_factory() as session:
        summary = await get_user_permission_summary(session, user_id=user_id)
        allowed = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="organization.member.manage",
        )
        denied = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="system.audit.view",
        )

    assert "organization.member.manage" in summary.permissions
    assert "system.audit.view" not in summary.permissions
    assert allowed.allowed is True
    assert denied.allowed is False

    await engine.dispose()


def test_permission_denied_dependency_writes_audit_log(tmp_path: Path) -> None:
    """HTTP 权限依赖拒绝访问时应写入审计日志。"""

    # 显式引用模型，确保 Base.metadata 收集认证、权限、审计和组织相关表。
    _ = (AuthSession, EmailVerificationCode, LocalAccount, WechatAccount, AuditLog, Position, UserPosition)

    database_path = tmp_path / "permission_denied.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def load_audit_logs() -> list[AuditLog]:
        async with session_factory() as session:
            result = await session.scalars(select(AuditLog).order_by(AuditLog.id))
            return list(result)

    asyncio.run(prepare_database())
    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/api/v1/auth/wechat/login",
                json={"dev_openid": "permission_denied_user"},
            )
            access_token = login_response.json()["data"]["access_token"]
            user_id = login_response.json()["data"]["user"]["id"]

            denied_response = client.get(
                "/api/v1/permissions",
                headers={"Authorization": f"Bearer {access_token}"},
            )
    finally:
        app.dependency_overrides.clear()

    logs = asyncio.run(load_audit_logs())
    asyncio.run(engine.dispose())

    assert denied_response.status_code == 403
    assert denied_response.json()["error"]["code"] == "PERMISSION_DENIED"
    assert len(logs) == 1
    assert logs[0].actor_id == user_id
    assert logs[0].action == "permission.denied"
    assert logs[0].result == "denied"
    assert logs[0].target_type == "permission"
    assert logs[0].target_id == "system.admin.access"
    assert logs[0].extra["path"] == "/api/v1/permissions"


@pytest.mark.asyncio
async def test_super_admin_position_has_mother_account_permissions_only() -> None:
    """999 是母账号，默认不自动拥有普通业务权限。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await sync_registered_permissions(session)
        user = User(display_name="超级管理员", status="active")
        position = Position(code="999", name="超级管理员", status="active", is_system=True)
        session.add_all([user, position])
        await session.flush()
        session.add(
            UserPosition(
                user_id=user.id,
                position_id=position.id,
                scope_type="global",
            ),
        )
        await session.commit()
        user_id = user.id

    async with session_factory() as session:
        operator_manage_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="system.operator.manage",
        )
        business_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="organization.member.manage",
        )
        summary = await get_user_permission_summary(session, user_id=user_id)

    assert operator_manage_decision.allowed is True
    assert business_decision.allowed is False
    assert summary.is_super_admin is True
    assert "system.operator.manage" in summary.permissions
    assert "organization.member.manage" not in summary.permissions

    await engine.dispose()


@pytest.mark.asyncio
async def test_system_operator_position_has_system_fallback_permissions_only() -> None:
    """998 由 999 指定，默认只拥有系统兜底权限。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await sync_registered_permissions(session)
        user = User(display_name="系统管理员", status="active")
        position = Position(code="998", name="管理员", status="active", is_system=True)
        session.add_all([user, position])
        await session.flush()
        session.add(
            UserPosition(
                user_id=user.id,
                position_id=position.id,
                scope_type="global",
            ),
        )
        await session.commit()
        user_id = user.id

    async with session_factory() as session:
        audit_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="system.audit.view",
        )
        operator_manage_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="system.operator.manage",
        )
        business_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="organization.member.manage",
        )
        summary = await get_user_permission_summary(session, user_id=user_id)

    assert audit_decision.allowed is True
    assert operator_manage_decision.allowed is False
    assert business_decision.allowed is False
    assert summary.is_super_admin is False
    assert summary.is_system_operator is True
    assert "system.audit.view" in summary.permissions
    assert "system.operator.manage" not in summary.permissions
    assert "organization.member.manage" not in summary.permissions

    await engine.dispose()
