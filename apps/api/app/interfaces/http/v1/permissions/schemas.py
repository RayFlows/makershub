# app/interfaces/http/v1/permissions/schemas.py
"""
权限接口响应模型

接口层 schema 只描述 HTTP 契约，权限授予、作用域匹配和 998/999 映射规则
由 core.permissions.service 负责。
"""

from __future__ import annotations

from pydantic import BaseModel


class PermissionItem(BaseModel):
    """权限点响应项。"""

    code: str
    name: str
    module: str
    description: str | None
    risk_level: str
    status: str


class RoleItem(BaseModel):
    """角色响应项。"""

    code: str
    name: str
    description: str | None
    is_system: bool
    status: str
    permissions: list[str]


class CurrentUserPermissions(BaseModel):
    """当前用户权限摘要响应。"""

    user_id: int
    permissions: list[str]
    is_super_admin: bool
    is_system_operator: bool
