# app/core/permissions/view.py
"""
权限视角工具

本文件处理“同一个接口根据权限返回不同范围”的通用判断。例如普通成员只能看到自己的
借用申请，而拥有审核权限的用户可以看全量；有全量权限的用户传 `mine=true` 时又应切回
本人视角。具体 SQL 过滤仍留在业务服务层，避免权限基础设施反向了解业务表结构。
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.permissions.service import check_user_permission


@dataclass(frozen=True)
class PermissionView:
    """接口调用者在某个列表或详情接口中的权限视角。"""

    can_view_all: bool
    owner_id: int | None


async def resolve_permission_view(
    session: AsyncSession,
    *,
    user_id: int,
    view_all_permission: str,
    mine: bool = False,
) -> PermissionView:
    """
    根据权限点和 mine 参数解析列表查询视角。

    `can_view_all=True` 表示业务服务可以不按本人过滤；`owner_id` 非空表示必须过滤到
    某个用户本人。业务服务应优先使用这个结果，而不是在 router 里散落权限判断。
    """

    decision = await check_user_permission(
        session,
        user_id=user_id,
        permission_code=view_all_permission,
    )
    can_view_all = decision.allowed and not mine
    return PermissionView(
        can_view_all=can_view_all,
        owner_id=None if can_view_all else user_id,
    )
