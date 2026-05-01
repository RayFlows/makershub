# app/modules/organization/service.py
"""
组织域业务服务

本模块承接成员资料、部门列表和部门成员关系的第一阶段业务规则。
身份登录不在这里处理；调用方必须先通过 identity 域确认当前用户是谁。
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.identity.models import User
from app.modules.organization.models import Department, DepartmentMembership, MemberProfile
from app.modules.organization.repository import OrganizationRepository


@dataclass(frozen=True)
class MemberProfileBundle:
    """当前成员资料页需要的聚合结果。"""

    profile: MemberProfile
    departments: list[Department]
    memberships: list[DepartmentMembership]


async def get_my_member_profile(session: AsyncSession, *, user: User) -> MemberProfileBundle:
    """
    获取当前登录用户的成员资料。

    如果用户已经能登录，但还没有成员资料记录，则懒创建一条空资料。
    这符合第一阶段“先建立用户主体，再逐步补齐协会资料”的链路。
    """

    repository = OrganizationRepository(session)
    profile = await repository.get_member_profile_by_user_id(user.id)
    if profile is None:
        profile = await repository.create_member_profile(
            user_id=user.id,
            email=user.local_account.email if user.local_account is not None else None,
        )

    departments = await repository.list_active_departments()
    memberships = await repository.list_user_department_memberships(user.id)
    return MemberProfileBundle(profile=profile, departments=departments, memberships=memberships)


async def list_active_departments(session: AsyncSession) -> list[Department]:
    """列出启用中的协会部门。"""

    repository = OrganizationRepository(session)
    return await repository.list_active_departments()


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

    repository = OrganizationRepository(session)
    profile = await repository.get_member_profile_by_user_id(user.id)
    if profile is None:
        profile = await repository.create_member_profile(
            user_id=user.id,
            email=user.local_account.email if user.local_account is not None else None,
        )

    update_data = normalize_member_profile_update(payload)
    for field, value in update_data.items():
        setattr(profile, field, value)

    await session.flush()
    # SQLAlchemy 更新带 onupdate 的时间字段后会过期该属性；异步接口层不能触发隐式 IO。
    await session.refresh(profile)
    departments = await repository.list_active_departments()
    memberships = await repository.list_user_department_memberships(user.id)
    return MemberProfileBundle(profile=profile, departments=departments, memberships=memberships)


def normalize_member_profile_update(payload: dict[str, str | None]) -> dict[str, str | None]:
    """
    规范化成员资料更新内容。

    空字符串会转为 None，避免数据库里长期保存不可见空白。
    """

    normalizers = {
        "real_name": lambda value: normalize_optional_text(value, max_length=100, field_label="真实姓名"),
        "student_id": lambda value: normalize_digits(value, max_length=32, field_label="学号"),
        "phone": normalize_phone,
        "email": lambda value: normalize_optional_text(value, max_length=255, field_label="联系邮箱"),
        "college": lambda value: normalize_optional_text(value, max_length=100, field_label="学院"),
        "major": lambda value: normalize_optional_text(value, max_length=100, field_label="专业"),
        "grade": lambda value: normalize_digits(value, max_length=20, field_label="年级"),
        "qq": lambda value: normalize_digits(value, max_length=20, field_label="QQ"),
        "bio": lambda value: normalize_optional_text(value, max_length=500, field_label="个人简介"),
    }
    return {field: normalizers[field](value) for field, value in payload.items() if field in normalizers}


def normalize_optional_text(value: str | None, *, max_length: int, field_label: str) -> str | None:
    """清理可选文本字段，并检查长度。"""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise AppError("MEMBER_PROFILE_FIELD_TOO_LONG", f"{field_label}过长", status_code=422)
    return normalized


def normalize_digits(value: str | None, *, max_length: int, field_label: str) -> str | None:
    """清理必须由数字组成的可选字段。"""

    normalized = normalize_optional_text(value, max_length=max_length, field_label=field_label)
    if normalized is None:
        return None
    if not normalized.isdigit():
        raise AppError("MEMBER_PROFILE_FIELD_INVALID", f"{field_label}必须由数字组成", status_code=422)
    return normalized


def normalize_phone(value: str | None) -> str | None:
    """
    清理手机号字段。

    当前先按中国大陆常见 11 位手机号校验，和旧小程序编辑页的校验保持一致。
    """

    normalized = normalize_optional_text(value, max_length=20, field_label="手机号")
    if normalized is None:
        return None
    if not re.fullmatch(r"1[3-9]\d{9}", normalized):
        raise AppError("MEMBER_PROFILE_PHONE_INVALID", "手机号格式不正确", status_code=422)
    return normalized
