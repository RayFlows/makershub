# app/modules/workbench/tasks/validators.py
"""
工作台任务校验工具

本文件承接任务模块中和状态机主流程相对独立的校验逻辑，包括字段枚举归一化和悬赏任务
领取范围判断。这样 service.py 可以专注描述“发布、领取、提交、审核”的业务流转，
避免随着工作台能力增加再次堆成难维护的大文件。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.identity.models import User
from app.modules.organization.positions.repository import PositionRepository
from app.modules.workbench.constants import (
    WORKBENCH_TASK_ASSIGNMENT_ASSIGNED,
    WORKBENCH_TASK_ASSIGNMENT_BOUNTY,
    WORKBENCH_TASK_REVIEW_APPROVE,
    WORKBENCH_TASK_REVIEW_REJECT,
    WORKBENCH_TASK_VISIBILITY_ASSOCIATION,
    WORKBENCH_TASK_VISIBILITY_DEPARTMENT,
    WORKBENCH_TASK_VISIBILITY_PUBLIC,
)
from app.modules.workbench.models import WorkbenchTask
from app.modules.workbench.utils import normalize_required_text

ASSOCIATION_MEMBER_POSITION_CODES = frozenset({"1", "2", "3", "4", "5"})
"""可以领取协会内任务的普通协会身份，不包含外部成员 0 和 998/999 系统身份。"""

SUPPORTED_ASSIGNMENT_TYPES = frozenset({WORKBENCH_TASK_ASSIGNMENT_ASSIGNED, WORKBENCH_TASK_ASSIGNMENT_BOUNTY})
"""当前任务闭环支持的分配方式。"""

SUPPORTED_VISIBILITIES = frozenset(
    {
        WORKBENCH_TASK_VISIBILITY_DEPARTMENT,
        WORKBENCH_TASK_VISIBILITY_ASSOCIATION,
        WORKBENCH_TASK_VISIBILITY_PUBLIC,
    },
)
"""当前任务闭环支持的可见范围。"""


# --- 悬赏领取范围 ---
async def ensure_user_can_claim_task(
    session: AsyncSession,
    *,
    user: User,
    task: WorkbenchTask,
) -> None:
    """
    确认用户可以领取目标悬赏任务。

    公开任务允许外部成员领取；协会内任务要求 1-5 普通协会身份；部门任务还必须落在
    用户当前有效部门职务范围内。998/999 是系统管理身份，不自动等同于业务领取资格。
    """

    if task.visibility == WORKBENCH_TASK_VISIBILITY_PUBLIC:
        return

    position_repository = PositionRepository(session)
    positions = await position_repository.list_user_positions(user.id)
    active_position_codes = {
        item.position.code
        for item in positions
        if item.position is not None and item.position.status == "active"
    }
    if not active_position_codes & ASSOCIATION_MEMBER_POSITION_CODES:
        raise AppError("WORKBENCH_TASK_CLAIM_FORBIDDEN", "当前任务不开放给外部成员领取", status_code=403)

    if task.visibility == WORKBENCH_TASK_VISIBILITY_DEPARTMENT:
        if task.department_id is None:
            raise AppError("WORKBENCH_TASK_DEPARTMENT_MISSING", "部门任务缺少部门范围", status_code=409)
        if not any(item.department_id == task.department_id for item in positions):
            raise AppError("WORKBENCH_TASK_DEPARTMENT_FORBIDDEN", "只能领取本部门任务", status_code=403)


# --- 枚举归一化 ---
def normalize_assignment_type(value: str) -> str:
    """清理任务分配方式。"""

    normalized = normalize_required_text(value, field_label="任务分配方式", max_length=32)
    if normalized not in SUPPORTED_ASSIGNMENT_TYPES:
        raise AppError("WORKBENCH_TASK_ASSIGNMENT_UNSUPPORTED", "暂不支持该任务分配方式", status_code=422)
    return normalized


def normalize_visibility(value: str) -> str:
    """清理任务可见范围。"""

    normalized = normalize_required_text(value, field_label="任务可见范围", max_length=32)
    if normalized not in SUPPORTED_VISIBILITIES:
        raise AppError("WORKBENCH_TASK_VISIBILITY_UNSUPPORTED", "暂不支持该任务可见范围", status_code=422)
    return normalized


def normalize_review_action(value: str) -> str:
    """清理任务审核动作。"""

    normalized = normalize_required_text(value, field_label="审核动作", max_length=32)
    if normalized not in {WORKBENCH_TASK_REVIEW_APPROVE, WORKBENCH_TASK_REVIEW_REJECT}:
        raise AppError("WORKBENCH_TASK_REVIEW_ACTION_UNSUPPORTED", "暂不支持该审核动作", status_code=422)
    return normalized
