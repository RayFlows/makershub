# app/modules/organization/departments/repository.py
"""
部门与部门成员关系仓储

本文件只封装 departments 和 department_memberships 的查询写入。是否允许调整部门、
是否需要审计，由服务层和接口层负责。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.organization.models import Department, DepartmentMembership
from app.shared.time import utc_now


class DepartmentRepository:
    """部门与部门成员关系仓储。"""

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

    async def get_department_by_id(self, department_id: int) -> Department | None:
        """按 ID 查询部门。"""

        statement = select(Department).where(Department.id == department_id)
        return await self.session.scalar(statement)

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

    async def list_active_department_memberships_by_user_ids(
        self,
        user_ids: list[int],
    ) -> list[DepartmentMembership]:
        """批量列出多个用户当前有效的部门关系。"""

        if not user_ids:
            return []
        statement = (
            select(DepartmentMembership)
            .options(selectinload(DepartmentMembership.department))
            .where(
                DepartmentMembership.user_id.in_(user_ids),
                DepartmentMembership.status == "active",
                DepartmentMembership.left_at.is_(None),
            )
            .order_by(DepartmentMembership.user_id.asc(), DepartmentMembership.joined_at.asc())
        )
        return list((await self.session.scalars(statement)).all())

    async def close_active_department_memberships(self, *, user_id: int) -> list[DepartmentMembership]:
        """结束用户当前所有有效部门关系，保留历史。"""

        memberships = await self.list_user_department_memberships(user_id)
        now = utc_now()
        for membership in memberships:
            membership.status = "inactive"
            membership.left_at = now
        return memberships

    async def create_department_membership(
        self,
        *,
        user_id: int,
        department_id: int,
    ) -> DepartmentMembership:
        """创建新的有效部门关系。"""

        membership = DepartmentMembership(
            user_id=user_id,
            department_id=department_id,
            status="active",
            joined_at=utc_now(),
        )
        self.session.add(membership)
        await self.session.flush()
        await self.session.refresh(membership, attribute_names=["department"])
        return membership
