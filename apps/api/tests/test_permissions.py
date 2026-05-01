# tests/test_permissions.py
"""
权限基础设施测试

当前只验证权限点注册表的基础行为。完整授权、角色和作用域规则会在权限系统
数据库表落地后继续补充测试。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.permissions import PermissionPoint, PermissionRegistry, PermissionRiskLevel, permission_registry
from app.core.permissions.models import Permission, Role
from app.core.permissions.repository import PermissionRepository
from app.core.permissions.service import (
    check_user_permission,
    get_user_permission_summary,
    sync_registered_permissions,
)
from app.core.database.base import Base
from app.modules.identity.models import User
from app.modules.organization.models import Position, UserPosition


def test_core_permission_registry_contains_required_points() -> None:
    """核心权限点应该在应用启动前完成注册。"""

    codes = {point.code for point in permission_registry.list()}

    assert "system.admin.access" in codes
    assert "system.audit.view" in codes
    assert "organization.member.manage" in codes
    assert "organization.department.manage" in codes
    assert "organization.position.manage" in codes
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
    with pytest.raises(ValueError):
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


@pytest.mark.asyncio
async def test_super_admin_position_bypasses_registered_permissions() -> None:
    """999 超级管理员只作为系统兜底身份，能够拿到全部注册权限点。"""

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
        decision = await check_user_permission(
            session,
            user_id=user_id,
            permission_code="files.upload",
        )
        summary = await get_user_permission_summary(session, user_id=user_id)

    assert decision.allowed is True
    assert summary.is_super_admin is True
    assert set(summary.permissions) == {point.code for point in permission_registry.list()}

    await engine.dispose()
