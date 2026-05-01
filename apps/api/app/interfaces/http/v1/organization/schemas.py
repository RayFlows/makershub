# app/interfaces/http/v1/organization/schemas.py
"""
组织与成员接口请求与响应模型

接口层 schema 只描述 HTTP 契约。成员资料能不能被修改、部门归属如何变更，
仍由 organization 服务层和后续权限模块共同决定。
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


class MyMemberProfileResponse(BaseModel):
    """当前成员资料页聚合响应。"""

    profile: MemberProfileResponse
    departments: list[DepartmentResponse]
    memberships: list[DepartmentMembershipResponse]


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
