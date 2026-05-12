# app/modules/organization/positions/service.py
"""
职务服务

本文件负责普通协会职务读取和成员职务替换。998/999 是底层系统身份，不属于日常成员
职务维护范围，不能通过这里授予或撤销。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.organization.departments.repository import DepartmentRepository
from app.modules.organization.members.service import get_member_detail, get_user_or_404
from app.modules.organization.models import Position
from app.modules.organization.positions.repository import PositionRepository
from app.modules.organization.types import MemberAdminBundle
from app.modules.organization.utils import normalize_position_codes


async def list_positions(session: AsyncSession) -> list[Position]:
    """
    列出后台可维护的协会职务。

    998/999 这类底层系统身份不会出现在这里，避免成员管理页误把系统兜底身份当作
    普通协会职务分配。
    """

    repository = PositionRepository(session)
    return await repository.list_positions(active_only=True, include_system=False)


async def replace_member_positions(
    session: AsyncSession,
    *,
    user_id: int,
    position_codes: list[str],
    granted_by: int,
    department_id: int | None = None,
) -> MemberAdminBundle:
    """
    替换成员当前协会职务。

    这里替换的是非系统职务，不能处理 998/999。若传入 department_id，则新授予的职务
    使用部门作用域；否则使用全局作用域。后续如果需要一个人同时拥有多个部门作用域职务，
    再拆成更细的增删接口。
    """

    user = await get_user_or_404(session, user_id=user_id)
    position_repository = PositionRepository(session)
    if department_id is not None:
        department_repository = DepartmentRepository(session)
        department = await department_repository.get_department_by_id(department_id)
        if department is None or department.status != "active":
            raise AppError("DEPARTMENT_NOT_FOUND", "部门不存在或未启用", status_code=404)

    normalized_codes = normalize_position_codes(position_codes)
    positions: list[Position] = []
    for code in normalized_codes:
        position = await position_repository.get_position_by_code(code)
        if position is None or position.status != "active":
            raise AppError("POSITION_NOT_FOUND", f"职务不存在或未启用: {code}", status_code=404)
        if position.is_system:
            raise AppError("SYSTEM_POSITION_FORBIDDEN", "998/999 不能通过成员职务接口维护", status_code=403)
        positions.append(position)

    scope_type = "department" if department_id is not None else "global"
    scope_id = department_id
    current_positions = await position_repository.list_user_positions(user.id, include_system=False)
    desired_keys = {(position.id, department_id, scope_type, scope_id) for position in positions}
    for user_position in current_positions:
        current_key = (
            user_position.position_id,
            user_position.department_id,
            user_position.scope_type,
            user_position.scope_id,
        )
        if current_key not in desired_keys:
            await position_repository.revoke_user_position(user_position)

    for position in positions:
        await position_repository.grant_user_position(
            user_id=user.id,
            position=position,
            granted_by=granted_by,
            department_id=department_id,
            scope_type=scope_type,
            scope_id=scope_id,
        )

    await session.flush()
    return await get_member_detail(session, user_id=user.id)
