# tests/test_permissions.py
"""
权限基础设施测试

当前只验证权限点注册表的基础行为。完整授权、角色和作用域规则会在权限系统
数据库表落地后继续补充测试。
"""

from __future__ import annotations

import pytest

from app.core.permissions import PermissionPoint, PermissionRegistry, PermissionRiskLevel, permission_registry


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
