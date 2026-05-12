# app/modules/organization/members/service.py
"""
成员资料服务

本文件处理当前成员自助资料、后台成员列表和后台成员基础资料维护。部门归属和职务关系
由 departments、positions 能力模块负责，避免一个服务函数同时跨多个高风险边界。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.identity.models import User
from app.modules.identity.repositories import IdentityRepository
from app.modules.organization.members.repository import MemberRepository
from app.modules.organization.models import MemberProfile
from app.modules.organization.types import (
    MemberAdminBundle,
    MemberListItemBundle,
    MemberListPage,
    MemberProfileBundle,
)
from app.modules.organization.utils import (
    group_by_user_id,
    normalize_member_profile_update,
    normalize_member_user_update,
)


async def get_my_member_profile(session: AsyncSession, *, user: User) -> MemberProfileBundle:
    """
    获取当前登录用户的成员资料。

    如果用户已经能登录，但还没有成员资料记录，则懒创建一条空资料。
    这符合第一阶段“先建立用户主体，再逐步补齐协会资料”的链路。
    """

    member_repository = MemberRepository(session)
    profile = await member_repository.get_member_profile_by_user_id(user.id)
    if profile is None:
        profile = await member_repository.create_member_profile(
            user_id=user.id,
            email=user.email_password_account.email if user.email_password_account is not None else None,
        )

    from app.modules.organization.departments.repository import DepartmentRepository

    department_repository = DepartmentRepository(session)
    departments = await department_repository.list_active_departments()
    memberships = await department_repository.list_user_department_memberships(user.id)
    return MemberProfileBundle(profile=profile, departments=departments, memberships=memberships)


async def list_members(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
) -> MemberListPage:
    """
    后台分页列出成员。

    列表以 users 为根，因为第一阶段允许用户先由微信登录创建，再逐步补齐成员资料。
    如果只从 member_profiles 出发，刚登录但资料未完善的用户会从后台管理视图中消失。
    """

    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    member_repository = MemberRepository(session)
    users, total = await member_repository.list_users(
        page=normalized_page,
        page_size=normalized_page_size,
        search=search,
    )
    user_ids = [user.id for user in users]
    profiles = await member_repository.list_member_profiles_by_user_ids(user_ids)
    from app.modules.organization.departments.repository import DepartmentRepository
    from app.modules.organization.positions.repository import PositionRepository

    department_repository = DepartmentRepository(session)
    memberships = await department_repository.list_active_department_memberships_by_user_ids(user_ids)
    position_repository = PositionRepository(session)
    positions = await position_repository.list_active_user_positions_by_user_ids(user_ids, include_system=False)

    profile_by_user_id = {profile.user_id: profile for profile in profiles}
    memberships_by_user_id = group_by_user_id(memberships)
    positions_by_user_id = group_by_user_id(positions)

    items = [
        MemberListItemBundle(
            user=user,
            profile=profile_by_user_id.get(user.id),
            memberships=memberships_by_user_id.get(user.id, []),
            positions=positions_by_user_id.get(user.id, []),
        )
        for user in users
    ]
    return MemberListPage(
        items=items,
        page=normalized_page,
        page_size=normalized_page_size,
        total=total,
    )


async def get_member_detail(session: AsyncSession, *, user_id: int) -> MemberAdminBundle:
    """获取后台成员详情。"""

    user = await get_user_or_404(session, user_id=user_id)
    member_repository = MemberRepository(session)
    profile = await get_or_create_member_profile(user=user, repository=member_repository)
    from app.modules.organization.departments.repository import DepartmentRepository
    from app.modules.organization.positions.repository import PositionRepository

    department_repository = DepartmentRepository(session)
    memberships = await department_repository.list_user_department_memberships(user.id)
    position_repository = PositionRepository(session)
    positions = await position_repository.list_user_positions(user.id, include_system=False)
    return MemberAdminBundle(user=user, profile=profile, memberships=memberships, positions=positions)


async def update_my_member_profile(
    session: AsyncSession,
    *,
    user: User,
    payload: dict[str, str | None],
) -> MemberProfileBundle:
    """
    更新当前登录用户自己的成员资料。

    旧小程序把个人资料直接写在 users 表；新实现只更新 member_profiles。
    管理他人资料、调整部门和授予职务必须走后续后台权限接口，不能混在自助资料接口里。
    """

    member_repository = MemberRepository(session)
    profile = await member_repository.get_member_profile_by_user_id(user.id)
    if profile is None:
        profile = await member_repository.create_member_profile(
            user_id=user.id,
            email=user.email_password_account.email if user.email_password_account is not None else None,
        )

    update_data = normalize_member_profile_update(payload)
    if "student_id" in update_data and update_data["student_id"] is not None:
        await ensure_student_id_available(
            session,
            student_id=update_data["student_id"],
            owner_user_id=user.id,
        )
    for field, value in update_data.items():
        setattr(profile, field, value)

    await session.flush()
    # SQLAlchemy 更新带 onupdate 的时间字段后会过期该属性；异步接口层不能触发隐式 IO。
    await session.refresh(profile)
    from app.modules.organization.departments.repository import DepartmentRepository

    department_repository = DepartmentRepository(session)
    departments = await department_repository.list_active_departments()
    memberships = await department_repository.list_user_department_memberships(user.id)
    return MemberProfileBundle(profile=profile, departments=departments, memberships=memberships)


async def update_member_by_admin(
    session: AsyncSession,
    *,
    user_id: int,
    payload: dict[str, str | None],
) -> MemberAdminBundle:
    """
    后台更新成员基础资料。

    该函数可以维护 users 上的展示名、状态和备注，也可以维护 member_profiles。
    部门归属和职务关系使用独立接口，避免一个 PATCH 请求同时改变多个高风险业务边界。
    """

    user = await get_user_or_404(session, user_id=user_id)
    member_repository = MemberRepository(session)
    profile = await get_or_create_member_profile(user=user, repository=member_repository)

    user_update = normalize_member_user_update(payload)
    for field, value in user_update.items():
        setattr(user, field, value)

    profile_update = normalize_member_profile_update(payload)
    if "student_id" in profile_update and profile_update["student_id"] is not None:
        await ensure_student_id_available(
            session,
            student_id=profile_update["student_id"],
            owner_user_id=user.id,
        )
    for field, value in profile_update.items():
        setattr(profile, field, value)

    await session.flush()
    await session.refresh(user)
    await session.refresh(profile)
    return await get_member_detail(session, user_id=user.id)


async def ensure_student_id_available(
    session: AsyncSession,
    *,
    student_id: str,
    owner_user_id: int,
) -> None:
    """检查学号是否已被其他用户资料占用。"""

    repository = MemberRepository(session)
    existing = await repository.get_member_profile_by_student_id(student_id)
    if existing is not None and existing.user_id != owner_user_id:
        raise AppError("MEMBER_STUDENT_ID_CONFLICT", "学号已被其他成员使用", status_code=409)


async def get_user_or_404(session: AsyncSession, *, user_id: int) -> User:
    """按用户 ID 获取用户主体，不存在时抛出业务错误。"""

    identity_repository = IdentityRepository(session)
    user = await identity_repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)
    return user


async def get_or_create_member_profile(
    *,
    user: User,
    repository: MemberRepository,
) -> MemberProfile:
    """获取或懒创建成员资料记录。"""

    profile = await repository.get_member_profile_by_user_id(user.id)
    if profile is not None:
        return profile
    return await repository.create_member_profile(
        user_id=user.id,
        email=user.email_password_account.email if user.email_password_account is not None else None,
    )
