# app/modules/organization/departments/service.py
"""
部门服务

本文件负责部门列表读取和成员部门归属调整。第一阶段采用“一个用户同一时间只有一个
主部门”的管理口径；历史部门关系保留，不直接删除。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.organization.departments.repository import DepartmentRepository
from app.modules.organization.members.service import get_member_detail, get_user_or_404
from app.modules.organization.models import Department
from app.modules.organization.types import MemberAdminBundle


async def list_active_departments(session: AsyncSession) -> list[Department]:
    """列出启用中的协会部门。"""

    repository = DepartmentRepository(session)
    return await repository.list_active_departments()


async def assign_member_department(
    session: AsyncSession,
    *,
    user_id: int,
    department_id: int | None,
) -> MemberAdminBundle:
    """
    调整成员当前部门归属。

    第一阶段采用“一个用户同一时间只有一个主部门”的管理口径；调整部门时会结束旧的
    有效部门关系，再创建新的有效关系。历史关系不删除，后续可用于审计和成员履历。
    """

    user = await get_user_or_404(session, user_id=user_id)
    repository = DepartmentRepository(session)
    if department_id is None:
        await repository.close_active_department_memberships(user_id=user.id)
        await session.flush()
        return await get_member_detail(session, user_id=user.id)

    department = await repository.get_department_by_id(department_id)
    if department is None or department.status != "active":
        raise AppError("DEPARTMENT_NOT_FOUND", "部门不存在或未启用", status_code=404)

    current = await repository.list_user_department_memberships(user.id)
    if len(current) == 1 and current[0].department_id == department.id:
        return await get_member_detail(session, user_id=user.id)

    await repository.close_active_department_memberships(user_id=user.id)
    await repository.create_department_membership(user_id=user.id, department_id=department.id)
    await session.flush()
    return await get_member_detail(session, user_id=user.id)
