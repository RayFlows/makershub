# app/core/permissions/__init__.py
"""
权限基础设施导出

当前包落地权限点注册表、权限数据库模型、角色授权服务和权限判断结果模型，
避免业务模块继续使用 `identity_code >= 1` 这类临时数字比较。
"""

from app.core.permissions.models import Permission, Role, RolePermission, UserRoleGrant
from app.core.permissions.registry import (
    PermissionPoint,
    PermissionRegistry,
    PermissionRiskLevel,
    permission_registry,
    register_core_permissions,
)
from app.core.permissions.service import (
    UserPermissionSummary,
    check_user_permission,
    get_user_permission_summary,
    sync_registered_permissions,
)
from app.core.permissions.types import PermissionDecision, PermissionScope

__all__ = [
    "PermissionDecision",
    "Permission",
    "PermissionPoint",
    "PermissionRegistry",
    "PermissionRiskLevel",
    "PermissionScope",
    "Role",
    "RolePermission",
    "UserPermissionSummary",
    "UserRoleGrant",
    "check_user_permission",
    "get_user_permission_summary",
    "permission_registry",
    "register_core_permissions",
    "sync_registered_permissions",
]
