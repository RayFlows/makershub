# app/core/permissions/__init__.py
"""
权限基础设施导出

当前包只落地权限点注册表和权限判断结果模型，避免业务模块继续使用
`identity_code >= 1` 这类临时数字比较。真正的用户授权、角色授权和作用域规则
会在后续权限数据库表与服务层中实现。
"""

from app.core.permissions.registry import (
    PermissionPoint,
    PermissionRegistry,
    PermissionRiskLevel,
    permission_registry,
    register_core_permissions,
)
from app.core.permissions.types import PermissionDecision, PermissionScope

__all__ = [
    "PermissionDecision",
    "PermissionPoint",
    "PermissionRegistry",
    "PermissionRiskLevel",
    "PermissionScope",
    "permission_registry",
    "register_core_permissions",
]
