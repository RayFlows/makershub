# app/interfaces/http/v1/organization/schemas.py
"""
组织与成员接口请求与响应模型

接口层 schema 只描述 HTTP 契约。成员资料能不能被修改、部门归属如何变更，
仍由 organization 域内 members、departments、positions 等能力模块和权限模块共同决定。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class DepartmentResponse(BaseModel):
    """部门摘要。"""

    id: int
    code: str
    name: str
    status: str
    sort_order: int


class MemberProfileResponse(BaseModel):
    """成员资料响应。"""

    id: int
    user_id: int
    real_name: str | None
    student_id: str | None
    phone: str | None
    email: str | None
    college: str | None
    major: str | None
    grade: str | None
    qq: str | None
    bio: str | None
    created_at: datetime
    updated_at: datetime


class DepartmentMembershipResponse(BaseModel):
    """部门成员关系响应。"""

    id: int
    department: DepartmentResponse
    status: str
    joined_at: datetime
    left_at: datetime | None


class PositionResponse(BaseModel):
    """协会职务定义响应。"""

    id: int
    code: str
    name: str
    status: str
    sort_order: int


class UserPositionResponse(BaseModel):
    """用户当前职务关系响应。"""

    id: int
    position: PositionResponse
    department: DepartmentResponse | None
    scope_type: str
    scope_id: int | None
    granted_by: int | None
    granted_at: datetime
    revoked_at: datetime | None


class MemberUserResponse(BaseModel):
    """后台成员管理中的用户主体摘要。"""

    id: int
    display_name: str
    avatar_url: str | None
    status: str
    email: str | None
    remark: str | None
    created_at: datetime
    updated_at: datetime


class MyMemberProfileResponse(BaseModel):
    """当前成员资料页聚合响应。"""

    profile: MemberProfileResponse
    departments: list[DepartmentResponse]
    memberships: list[DepartmentMembershipResponse]


class MemberAdminResponse(BaseModel):
    """后台成员详情响应。"""

    user: MemberUserResponse
    profile: MemberProfileResponse
    memberships: list[DepartmentMembershipResponse]
    positions: list[UserPositionResponse]


class MemberListItemResponse(BaseModel):
    """后台成员列表响应项。"""

    user: MemberUserResponse
    profile: MemberProfileResponse | None
    memberships: list[DepartmentMembershipResponse]
    positions: list[UserPositionResponse]


class MemberListResponse(BaseModel):
    """后台成员列表分页响应。"""

    items: list[MemberListItemResponse]
    page: int
    page_size: int
    total: int


class UpdateMyMemberProfileRequest(BaseModel):
    """更新当前成员资料请求。"""

    real_name: str | None = Field(default=None, max_length=100, description="真实姓名")
    student_id: str | None = Field(default=None, max_length=32, description="学号")
    phone: str | None = Field(default=None, max_length=20, description="手机号")
    email: str | None = Field(default=None, max_length=255, description="联系邮箱")
    college: str | None = Field(default=None, max_length=100, description="学院")
    major: str | None = Field(default=None, max_length=100, description="专业")
    grade: str | None = Field(default=None, max_length=20, description="年级")
    qq: str | None = Field(default=None, max_length=20, description="QQ")
    bio: str | None = Field(default=None, max_length=500, description="个人简介")


class UpdateMemberRequest(UpdateMyMemberProfileRequest):
    """后台更新成员基础资料请求。"""

    display_name: str | None = Field(default=None, max_length=80, description="展示名")
    status: str | None = Field(default=None, max_length=32, description="用户状态")
    remark: str | None = Field(default=None, max_length=500, description="后台备注")
    reason: str | None = Field(default=None, max_length=255, description="修改原因")


class AssignMemberDepartmentRequest(BaseModel):
    """后台调整成员部门请求。"""

    department_id: int | None = Field(default=None, description="目标部门 ID；为空表示清除当前部门")
    reason: str | None = Field(default=None, max_length=255, description="调整原因")


class ReplaceMemberPositionsRequest(BaseModel):
    """后台替换成员当前职务请求。"""

    position_codes: list[str] = Field(default_factory=list, description="目标职务 code 列表")
    department_id: int | None = Field(default=None, description="部门作用域 ID；为空表示全局职务")
    reason: str | None = Field(default=None, max_length=255, description="调整原因")
