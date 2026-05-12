# app/modules/organization/types.py
"""
组织域服务层结果对象

组织域的接口通常需要聚合用户主体、成员资料、部门关系和职务关系。这里用明确的
数据结构描述服务层返回值，避免接口层直接拼装多个仓储查询结果。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.identity.models import User
from app.modules.organization.models import Department, DepartmentMembership, MemberProfile, UserPosition


@dataclass(frozen=True)
class MemberProfileBundle:
    """当前成员资料页需要的聚合结果。"""

    profile: MemberProfile
    departments: list[Department]
    memberships: list[DepartmentMembership]


@dataclass(frozen=True)
class MemberAdminBundle:
    """后台成员管理详情需要的聚合结果。"""

    user: User
    profile: MemberProfile
    memberships: list[DepartmentMembership]
    positions: list[UserPosition]


@dataclass(frozen=True)
class MemberListItemBundle:
    """后台成员列表中的单个成员聚合结果。"""

    user: User
    profile: MemberProfile | None
    memberships: list[DepartmentMembership]
    positions: list[UserPosition]


@dataclass(frozen=True)
class MemberListPage:
    """后台成员列表分页结果。"""

    items: list[MemberListItemBundle]
    page: int
    page_size: int
    total: int
