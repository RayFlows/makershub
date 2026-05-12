# app/interfaces/http/v1/organization/router.py
"""
组织与成员 V1 路由

第一阶段先提供当前成员自己的资料和部门列表，用于成员网页端跑通资料闭环。
后台成员管理、部门调整和职务授予必须经过权限点和审计日志，避免组织基础数据被
无痕修改。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security.middleware import get_client_ip
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.organization.schemas import (
    AssignMemberDepartmentRequest,
    DepartmentMembershipResponse,
    DepartmentResponse,
    MemberAdminResponse,
    MemberListItemResponse,
    MemberListResponse,
    MemberProfileResponse,
    MemberUserResponse,
    MyMemberProfileResponse,
    PositionResponse,
    ReplaceMemberPositionsRequest,
    UpdateMemberRequest,
    UpdateMyMemberProfileRequest,
    UserPositionResponse,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.identity.models import User
from app.modules.organization.departments import assign_member_department, list_active_departments
from app.modules.organization.members import (
    get_member_detail,
    get_my_member_profile,
    list_members,
    update_member_by_admin,
    update_my_member_profile,
)
from app.modules.organization.models import Department, DepartmentMembership, MemberProfile, Position, UserPosition
from app.modules.organization.positions import list_positions, replace_member_positions
from app.modules.organization.types import MemberAdminBundle, MemberListItemBundle
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


# --- 响应转换 ---
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


def build_position_response(position: Position) -> PositionResponse:
    """把职务定义 ORM 对象转换成接口响应。"""

    return PositionResponse(
        id=position.id,
        code=position.code,
        name=position.name,
        status=position.status,
        sort_order=position.sort_order,
    )


def build_user_position_response(user_position: UserPosition) -> UserPositionResponse:
    """把用户职务关系 ORM 对象转换成接口响应。"""

    return UserPositionResponse(
        id=user_position.id,
        position=build_position_response(user_position.position),
        department=(
            build_department_response(user_position.department) if user_position.department is not None else None
        ),
        scope_type=user_position.scope_type,
        scope_id=user_position.scope_id,
        granted_by=user_position.granted_by,
        granted_at=user_position.granted_at,
        revoked_at=user_position.revoked_at,
    )


def build_member_user_response(user: User) -> MemberUserResponse:
    """把用户主体转换成后台成员摘要。"""

    return MemberUserResponse(
        id=user.id,
        display_name=user.display_name,
        avatar_url=user.avatar_url,
        status=user.status,
        email=user.email_password_account.email if user.email_password_account is not None else None,
        remark=user.remark,
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def build_my_member_profile_response(bundle) -> MyMemberProfileResponse:
    """把服务层聚合结果转换成当前成员资料响应。"""

    return MyMemberProfileResponse(
        profile=build_member_profile_response(bundle.profile),
        departments=[build_department_response(department) for department in bundle.departments],
        memberships=[build_department_membership_response(item) for item in bundle.memberships],
    )


def build_member_admin_response(bundle: MemberAdminBundle) -> MemberAdminResponse:
    """把后台成员详情聚合结果转换成接口响应。"""

    return MemberAdminResponse(
        user=build_member_user_response(bundle.user),
        profile=build_member_profile_response(bundle.profile),
        memberships=[build_department_membership_response(item) for item in bundle.memberships],
        positions=[build_user_position_response(item) for item in bundle.positions],
    )


def build_member_list_item_response(bundle: MemberListItemBundle) -> MemberListItemResponse:
    """把后台成员列表聚合项转换成接口响应。"""

    return MemberListItemResponse(
        user=build_member_user_response(bundle.user),
        profile=build_member_profile_response(bundle.profile) if bundle.profile is not None else None,
        memberships=[build_department_membership_response(item) for item in bundle.memberships],
        positions=[build_user_position_response(item) for item in bundle.positions],
    )


def build_member_audit_snapshot(bundle: MemberAdminBundle) -> dict:
    """构造组织成员变更审计快照。"""

    return build_member_admin_response(bundle).model_dump(mode="json")


# --- 基础字典与当前成员资料 ---
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


@router.get("/positions")
async def get_positions(
    request: Request,
    _: CurrentUser = Depends(require_permission("system.admin.access")),
    session: AsyncSession = Depends(get_session),
):
    """
    获取后台可维护的协会职务列表。

    该接口不返回 998/999 系统底层身份，它们必须走专门的系统身份维护流程。
    """

    positions = await list_positions(session)
    data = [build_position_response(position).model_dump(mode="json") for position in positions]
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


# --- 后台成员管理 ---
@router.get("/members")
async def get_members(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    search: str | None = Query(default=None, max_length=100),
    _: CurrentUser = Depends(require_permission("organization.member.manage")),
    session: AsyncSession = Depends(get_session),
):
    """后台分页查看成员列表。"""

    page_data = await list_members(session, page=page, page_size=page_size, search=search)
    data = MemberListResponse(
        items=[build_member_list_item_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/members/{member_id}")
async def get_member(
    member_id: int,
    request: Request,
    _: CurrentUser = Depends(require_permission("organization.member.manage")),
    session: AsyncSession = Depends(get_session),
):
    """后台查看成员详情。"""

    bundle = await get_member_detail(session, user_id=member_id)
    await session.commit()
    data = build_member_admin_response(bundle)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.patch("/members/{member_id}")
async def update_member(
    member_id: int,
    payload: UpdateMemberRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("organization.member.manage")),
    session: AsyncSession = Depends(get_session),
):
    """后台更新成员基础资料，并写入审计日志。"""

    before_snapshot = build_member_audit_snapshot(await get_member_detail(session, user_id=member_id))
    update_data = payload.model_dump(exclude_unset=True)
    bundle = await update_member_by_admin(session, user_id=member_id, payload=update_data)
    after_snapshot = build_member_audit_snapshot(bundle)
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="organization.member.update",
            target_type="user",
            target_id=str(member_id),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="medium",
        ),
    )
    await session.commit()
    return success_response(after_snapshot, request_id=get_request_id(request))


@router.patch("/members/{member_id}/department")
async def update_member_department(
    member_id: int,
    payload: AssignMemberDepartmentRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("organization.department.manage")),
    session: AsyncSession = Depends(get_session),
):
    """后台调整成员部门归属，并写入审计日志。"""

    before_snapshot = build_member_audit_snapshot(await get_member_detail(session, user_id=member_id))
    bundle = await assign_member_department(
        session,
        user_id=member_id,
        department_id=payload.department_id,
    )
    after_snapshot = build_member_audit_snapshot(bundle)
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="organization.member.department.assign",
            target_type="user",
            target_id=str(member_id),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    return success_response(after_snapshot, request_id=get_request_id(request))


@router.patch("/members/{member_id}/positions")
async def update_member_positions(
    member_id: int,
    payload: ReplaceMemberPositionsRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("organization.position.manage")),
    session: AsyncSession = Depends(get_session),
):
    """
    后台替换成员当前协会职务，并写入审计日志。

    998/999 系统身份不允许通过该接口维护。
    """

    before_snapshot = build_member_audit_snapshot(await get_member_detail(session, user_id=member_id))
    bundle = await replace_member_positions(
        session,
        user_id=member_id,
        position_codes=payload.position_codes,
        granted_by=current_user.user.id,
        department_id=payload.department_id,
    )
    after_snapshot = build_member_audit_snapshot(bundle)
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="organization.member.positions.replace",
            target_type="user",
            target_id=str(member_id),
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    return success_response(after_snapshot, request_id=get_request_id(request))
