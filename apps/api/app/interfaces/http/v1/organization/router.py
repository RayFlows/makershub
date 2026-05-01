# app/interfaces/http/v1/organization/router.py
"""
组织与成员 V1 路由

第一阶段先提供当前成员自己的资料和部门列表，用于成员网页端跑通资料闭环。
后台成员管理、部门调整和职务授予后续必须接入权限点后再开放。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.interfaces.http.dependencies import CurrentUser, get_current_user
from app.interfaces.http.v1.organization.schemas import (
    DepartmentMembershipResponse,
    DepartmentResponse,
    MemberProfileResponse,
    MyMemberProfileResponse,
    UpdateMyMemberProfileRequest,
)
from app.modules.organization.models import Department, DepartmentMembership, MemberProfile
from app.modules.organization.service import get_my_member_profile, list_active_departments, update_my_member_profile
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


def build_department_response(department: Department) -> DepartmentResponse:
    """把部门 ORM 对象转换成接口响应。"""

    return DepartmentResponse(
        id=department.id,
        code=department.code,
        name=department.name,
        status=department.status,
        sort_order=department.sort_order,
    )


def build_member_profile_response(profile: MemberProfile) -> MemberProfileResponse:
    """把成员资料 ORM 对象转换成接口响应。"""

    return MemberProfileResponse(
        id=profile.id,
        user_id=profile.user_id,
        real_name=profile.real_name,
        student_id=profile.student_id,
        phone=profile.phone,
        email=profile.email,
        college=profile.college,
        major=profile.major,
        grade=profile.grade,
        qq=profile.qq,
        bio=profile.bio,
        created_at=profile.created_at,
        updated_at=profile.updated_at,
    )


def build_department_membership_response(
    membership: DepartmentMembership,
) -> DepartmentMembershipResponse:
    """把部门成员关系 ORM 对象转换成接口响应。"""

    return DepartmentMembershipResponse(
        id=membership.id,
        department=build_department_response(membership.department),
        status=membership.status,
        joined_at=membership.joined_at,
        left_at=membership.left_at,
    )


def build_my_member_profile_response(bundle) -> MyMemberProfileResponse:
    """把服务层聚合结果转换成当前成员资料响应。"""

    return MyMemberProfileResponse(
        profile=build_member_profile_response(bundle.profile),
        departments=[build_department_response(department) for department in bundle.departments],
        memberships=[build_department_membership_response(item) for item in bundle.memberships],
    )


@router.get("/departments")
async def get_departments(
    request: Request,
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    获取启用中的协会部门列表。

    当前先要求登录访问，避免第一阶段在没有权限系统前暴露内部组织基础数据。
    """

    departments = await list_active_departments(session)
    data = [build_department_response(department).model_dump(mode="json") for department in departments]
    return success_response(data, request_id=get_request_id(request))


@router.get("/me/profile")
async def get_my_profile(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """获取当前登录用户的成员资料。"""

    bundle = await get_my_member_profile(session, user=current_user.user)
    await session.commit()
    data = build_my_member_profile_response(bundle)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.patch("/me/profile")
async def update_my_profile(
    payload: UpdateMyMemberProfileRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """更新当前登录用户的成员资料。"""

    update_data = payload.model_dump(exclude_unset=True)
    bundle = await update_my_member_profile(session, user=current_user.user, payload=update_data)
    await session.commit()
    data = build_my_member_profile_response(bundle)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))
