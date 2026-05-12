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
from app.core.permissions.models import Permission, Role, RolePermission, UserRoleGrant
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import (
    check_user_permission,
    get_user_permission_summary,
    sync_registered_permissions,
)
from app.main import create_app
from app.modules.audit.models import AuditLog
from app.modules.identity.models import AuthSession, EmailPasswordAccount, EmailVerificationCode, User, WechatAccount
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
    assert "points.ledger.view" in codes
    assert "points.rule.view" in codes
    assert "points.rule.manage" in codes
    assert "points.temporary_rule.apply" in codes
    assert "points.temporary_rule.review" in codes
    assert "points.manual.adjust" in codes
    assert "workbench.task.publish" in codes


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
        repository = PermissionRepository(session)
        roles = await repository.list_roles()

    assert result.permission_count == len(permission_registry.list())
    assert second_result.permission_count == result.permission_count
    assert result.role_count >= 5
    assert {item.code for item in permissions} >= {"system.admin.access", "files.manage"}
    assert {item.code for item in roles} >= {
        "system_super_admin",
        "organization_manager",
        "points_manager",
        "points_rule_applicant",
        "points_rule_reviewer",
        "points_rule_manager",
        "workbench_task_publisher",
    }

    workbench_role = next(item for item in roles if item.code == "workbench_task_publisher")
    permission_codes = {
        relation.permission.code
        for relation in workbench_role.role_permissions
        if relation.permission is not None
    }
    assert permission_codes >= {"workbench.task.publish", "points.rule.view"}

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
    _ = (AuthSession, EmailVerificationCode, EmailPasswordAccount, WechatAccount, AuditLog, Position, UserPosition)

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


def test_permission_role_write_api_grants_and_revokes_with_audit(tmp_path: Path) -> None:
    """权限写接口应该授予业务角色、撤销授权，并记录审计日志。"""

    _ = (
        AuthSession,
        AuditLog,
        EmailVerificationCode,
        EmailPasswordAccount,
        Permission,
        Position,
        Role,
        RolePermission,
        UserPosition,
        UserRoleGrant,
        WechatAccount,
    )

    database_path = tmp_path / "permission_write.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            await sync_registered_permissions(session)
            await session.commit()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def grant_bootstrap_role(user_id: int) -> None:
        async with session_factory() as session:
            repository = PermissionRepository(session)
            role = await repository.get_role_by_code("system_super_admin")
            assert role is not None
            await repository.grant_role_to_user(user_id=user_id, role=role)
            await session.commit()

    async def load_audit_logs() -> list[AuditLog]:
        async with session_factory() as session:
            result = await session.scalars(select(AuditLog).order_by(AuditLog.id))
            return list(result)

    asyncio.run(prepare_database())
    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as client:
            admin_login = client.post(
                "/api/v1/auth/wechat/login",
                json={"dev_openid": "permission_write_admin"},
            )
            target_login = client.post(
                "/api/v1/auth/wechat/login",
                json={"dev_openid": "permission_write_target"},
            )
            admin_token = admin_login.json()["data"]["access_token"]
            admin_id = admin_login.json()["data"]["user"]["id"]
            target_id = target_login.json()["data"]["user"]["id"]
            asyncio.run(grant_bootstrap_role(admin_id))

            grant_response = client.post(
                f"/api/v1/permissions/users/{target_id}/roles",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"role_code": "organization_manager", "reason": "授予组织管理测试角色"},
            )
            assert grant_response.status_code == 200
            user_role_grant_id = grant_response.json()["data"]["id"]

            roles_response = client.get(
                f"/api/v1/permissions/users/{target_id}/roles",
                headers={"Authorization": f"Bearer {admin_token}"},
            )

            revoke_response = client.post(
                f"/api/v1/permissions/role-grants/{user_role_grant_id}/revoke",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"reason": "撤销组织管理测试角色"},
            )
    finally:
        app.dependency_overrides.clear()

    logs = asyncio.run(load_audit_logs())
    asyncio.run(engine.dispose())

    assert grant_response.status_code == 200
    assert grant_response.json()["data"]["role_code"] == "organization_manager"
    assert roles_response.status_code == 200
    assert roles_response.json()["data"]["roles"][0]["role_code"] == "organization_manager"
    assert revoke_response.status_code == 200
    assert revoke_response.json()["data"]["revoked_at"] is not None
    assert [log.action for log in logs] == [
        "permission.user_role_grant.create",
        "permission.user_role_grant.revoke",
    ]


def test_permission_role_write_api_rejects_system_operator_roles(tmp_path: Path) -> None:
    """普通权限写接口不能授予 998/999 底层系统角色。"""

    _ = (
        AuthSession,
        AuditLog,
        EmailVerificationCode,
        EmailPasswordAccount,
        Permission,
        Position,
        Role,
        RolePermission,
        UserPosition,
        UserRoleGrant,
        WechatAccount,
    )

    database_path = tmp_path / "permission_system_role.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            await sync_registered_permissions(session)
            await session.commit()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    async def grant_bootstrap_role(user_id: int) -> None:
        async with session_factory() as session:
            repository = PermissionRepository(session)
            role = await repository.get_role_by_code("system_super_admin")
            assert role is not None
            await repository.grant_role_to_user(user_id=user_id, role=role)
            await session.commit()

    asyncio.run(prepare_database())
    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as client:
            admin_login = client.post(
                "/api/v1/auth/wechat/login",
                json={"dev_openid": "permission_system_role_admin"},
            )
            target_login = client.post(
                "/api/v1/auth/wechat/login",
                json={"dev_openid": "permission_system_role_target"},
            )
            admin_token = admin_login.json()["data"]["access_token"]
            admin_id = admin_login.json()["data"]["user"]["id"]
            target_id = target_login.json()["data"]["user"]["id"]
            asyncio.run(grant_bootstrap_role(admin_id))

            response = client.post(
                f"/api/v1/permissions/users/{target_id}/roles",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"role_code": "system_operator", "reason": "错误指定 998"},
            )
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SYSTEM_ROLE_GRANT_FORBIDDEN"


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
        manual_adjust_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="points.manual.adjust",
        )
        summary = await get_user_permission_summary(session, user_id=user_id)

    assert operator_manage_decision.allowed is True
    assert business_decision.allowed is False
    assert manual_adjust_decision.allowed is True
    assert summary.is_super_admin is True
    assert "system.operator.manage" in summary.permissions
    assert "points.manual.adjust" in summary.permissions
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
        manual_adjust_decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="points.manual.adjust",
        )
        summary = await get_user_permission_summary(session, user_id=user_id)

    assert audit_decision.allowed is True
    assert operator_manage_decision.allowed is False
    assert business_decision.allowed is False
    assert manual_adjust_decision.allowed is True
    assert summary.is_super_admin is False
    assert summary.is_system_operator is True
    assert "system.audit.view" in summary.permissions
    assert "system.operator.manage" not in summary.permissions
    assert "points.manual.adjust" in summary.permissions
    assert "organization.member.manage" not in summary.permissions

    await engine.dispose()
