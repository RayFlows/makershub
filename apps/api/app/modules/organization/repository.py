# app/modules/organization/repository.py
"""
组织域数据访问层

Repository 只封装部门、成员资料和部门关系的数据库读写，不直接决定业务流程。
这样后续后台成员管理、花名册、部门调动和权限作用域可以复用同一组查询方法。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.organization.models import Department, DepartmentMembership, MemberProfile


class OrganizationRepository:
    """组织域数据库操作集合。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def list_active_departments(self) -> list[Department]:
        """按展示顺序列出启用中的协会部门。"""

        statement = (
            select(Department)
            .where(Department.status == "active")
            .order_by(Department.sort_order.asc(), Department.id.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def get_member_profile_by_user_id(self, user_id: int) -> MemberProfile | None:
        """按内部用户主键查找成员资料。"""

        statement = select(MemberProfile).where(MemberProfile.user_id == user_id)
        return await self.session.scalar(statement)

    async def create_member_profile(self, *, user_id: int, email: str | None = None) -> MemberProfile:
        """为已有用户主体创建成员资料。"""

        profile = MemberProfile(user_id=user_id, email=email)
        self.session.add(profile)
        await self.session.flush()
        # 迁移使用数据库默认时间字段；显式刷新避免异步响应序列化时触发隐式 IO。
        await self.session.refresh(profile)
        return profile

    async def list_user_department_memberships(self, user_id: int) -> list[DepartmentMembership]:
        """列出某用户当前有效的部门成员关系。"""

        statement = (
            select(DepartmentMembership)
            .options(selectinload(DepartmentMembership.department))
            .where(
                DepartmentMembership.user_id == user_id,
                DepartmentMembership.status == "active",
                DepartmentMembership.left_at.is_(None),
            )
            .order_by(DepartmentMembership.joined_at.asc(), DepartmentMembership.id.asc())
        )
        return list((await self.session.scalars(statement)).all())
