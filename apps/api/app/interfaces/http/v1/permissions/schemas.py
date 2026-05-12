# app/interfaces/http/v1/permissions/schemas.py
"""
权限接口响应模型

接口层 schema 只描述 HTTP 契约，权限授予、作用域匹配和 998/999 映射规则
由 core.permissions.service 负责。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


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


class UserRoleGrantItem(BaseModel):
    """用户角色授权响应项。"""

    id: int
    user_id: int
    role_code: str
    role_name: str
    scope_type: str
    scope_id: int | None
    granted_by: int | None
    granted_at: datetime
    revoked_at: datetime | None


class GrantUserRoleRequest(BaseModel):
    """授予用户角色请求。"""

    role_code: str = Field(min_length=1, max_length=64, description="角色 code")
    scope_type: str = Field(default="global", max_length=32, description="作用域类型")
    scope_id: int | None = Field(default=None, description="作用域 ID，全局授权为空")
    reason: str | None = Field(default=None, max_length=255, description="授权原因")


class RevokeUserRoleGrantRequest(BaseModel):
    """撤销用户角色请求。"""

    reason: str | None = Field(default=None, max_length=255, description="撤销原因")
