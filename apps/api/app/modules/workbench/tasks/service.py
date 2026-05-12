# app/modules/workbench/tasks/service.py
"""
工作台任务服务

本文件实现任务发布、领取、提交和审核发分。它参考旧任务模块的“发布给负责人、查看我
的任务、管理全部任务”语义，但按新版需求把完成流程拆成提交与审核，并强制任务积分
来自积分规则，不能在任务发布时临时改分。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.identity.models import User
from app.modules.identity.repositories import IdentityRepository
from app.modules.organization.models import Department
from app.modules.points.constants import POINT_RULE_STATUS_ACTIVE
from app.modules.points.rules import grant_points_by_rule
from app.modules.points.rules.repository import PointRuleRepository
from app.modules.workbench.constants import (
    WORKBENCH_TASK_ASSIGNMENT_ASSIGNED,
    WORKBENCH_TASK_ASSIGNMENT_BOUNTY,
    WORKBENCH_TASK_REVIEW_REJECT,
    WORKBENCH_TASK_STATUS_COMPLETED,
    WORKBENCH_TASK_STATUS_PENDING_CLAIM,
    WORKBENCH_TASK_STATUS_PENDING_COMPLETION,
    WORKBENCH_TASK_STATUS_PENDING_REVIEW,
    WORKBENCH_TASK_STATUS_REJECTED,
    WORKBENCH_TASK_STATUS_RULE_REVOKED_PENDING,
    WORKBENCH_TASK_VISIBILITY_DEPARTMENT,
)
from app.modules.workbench.models import WorkbenchTask
from app.modules.workbench.tasks.repository import WorkbenchTaskRepository
from app.modules.workbench.tasks.validators import (
    ensure_user_can_claim_task,
    normalize_assignment_type,
    normalize_review_action,
    normalize_visibility,
)
from app.modules.workbench.types import WorkbenchTaskPage
from app.modules.workbench.utils import normalize_optional_text, normalize_required_text
from app.shared.time import utc_now


# --- 任务查询与发布 ---
async def list_workbench_tasks(
    session: AsyncSession,
    *,
    viewer_id: int,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    mine: bool = False,
    available_to_claim: bool = False,
) -> WorkbenchTaskPage:
    """分页查询工作台任务。"""

    await _get_user_or_404(session, user_id=viewer_id)
    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    normalized_status = normalize_optional_text(status, field_label="任务状态", max_length=40)
    repository = WorkbenchTaskRepository(session)
    items, total = await repository.list_tasks(
        page=normalized_page,
        page_size=normalized_page_size,
        viewer_id=viewer_id,
        status=normalized_status,
        mine=mine,
        available_to_claim=available_to_claim,
    )
    return WorkbenchTaskPage(
        items=items,
        page=normalized_page,
        page_size=normalized_page_size,
        total=total,
    )


async def publish_workbench_task(
    session: AsyncSession,
    *,
    publisher_id: int,
    title: str,
    task_type: str,
    assignment_type: str,
    visibility: str,
    content: str,
    point_rule_id: int,
    assignee_id: int | None = None,
    department_id: int | None = None,
    deadline: datetime | None = None,
) -> WorkbenchTask:
    """
    发布工作台任务。

    指定任务必须传入执行人，发布后直接待完成；悬赏任务不能预设执行人，发布后待领取。
    两类任务都必须引用已启用积分规则，发布人不能在任务上单独填写积分数。
    """

    publisher = await _get_user_or_404(session, user_id=publisher_id)
    point_rule_repository = PointRuleRepository(session)
    point_rule = await point_rule_repository.get_point_rule_by_id(point_rule_id)
    if point_rule is None:
        raise AppError("WORKBENCH_POINT_RULE_NOT_FOUND", "任务引用的积分规则不存在", status_code=404)
    if point_rule.status != POINT_RULE_STATUS_ACTIVE:
        raise AppError("WORKBENCH_POINT_RULE_NOT_ACTIVE", "任务引用的积分规则未启用或已撤回", status_code=409)

    normalized_title = normalize_required_text(title, field_label="任务标题", max_length=120)
    normalized_task_type = normalize_required_text(task_type, field_label="任务类型", max_length=64)
    normalized_assignment_type = normalize_assignment_type(assignment_type)
    normalized_visibility = normalize_visibility(visibility)
    normalized_content = normalize_required_text(content, field_label="任务内容", max_length=2000)
    if normalized_visibility == WORKBENCH_TASK_VISIBILITY_DEPARTMENT and department_id is None:
        raise AppError("WORKBENCH_TASK_DEPARTMENT_REQUIRED", "部门任务必须指定部门", status_code=422)
    if department_id is not None:
        await _ensure_department_exists(session, department_id=department_id)

    if normalized_assignment_type == WORKBENCH_TASK_ASSIGNMENT_ASSIGNED:
        if assignee_id is None:
            raise AppError("WORKBENCH_TASK_ASSIGNEE_REQUIRED", "指定任务必须选择执行人", status_code=422)
        assignee = await _get_user_or_404(session, user_id=assignee_id)
        _ensure_different_active_user(publisher=publisher, assignee=assignee)
        status = WORKBENCH_TASK_STATUS_PENDING_COMPLETION
    else:
        if assignee_id is not None:
            raise AppError("WORKBENCH_TASK_ASSIGNEE_FORBIDDEN", "悬赏任务发布时不能预设执行人", status_code=422)
        status = WORKBENCH_TASK_STATUS_PENDING_CLAIM

    task = WorkbenchTask(
        title=normalized_title,
        task_type=normalized_task_type,
        assignment_type=normalized_assignment_type,
        visibility=normalized_visibility,
        department_id=department_id,
        content=normalized_content,
        deadline=deadline,
        status=status,
        publisher_id=publisher_id,
        assignee_id=assignee_id,
        point_rule=point_rule,
    )
    repository = WorkbenchTaskRepository(session)
    return await repository.add_task(task)


# --- 任务领取、提交和审核 ---
async def claim_workbench_task(
    session: AsyncSession,
    *,
    task_id: int,
    claimant_id: int,
) -> WorkbenchTask:
    """领取悬赏任务，领取后直接进入待完成。"""

    claimant = await _get_user_or_404(session, user_id=claimant_id)
    repository = WorkbenchTaskRepository(session)
    task = await _get_task_or_404(repository, task_id=task_id, for_update=True)
    if task.assignment_type != WORKBENCH_TASK_ASSIGNMENT_BOUNTY:
        raise AppError("WORKBENCH_TASK_NOT_BOUNTY", "只有悬赏任务可以领取", status_code=409)
    if task.status != WORKBENCH_TASK_STATUS_PENDING_CLAIM:
        raise AppError("WORKBENCH_TASK_NOT_CLAIMABLE", "任务当前不可领取", status_code=409)
    if task.publisher_id == claimant_id:
        raise AppError("WORKBENCH_TASK_CLAIM_SELF_FORBIDDEN", "任务发布人不能领取自己的任务", status_code=409)

    await ensure_user_can_claim_task(session, user=claimant, task=task)
    task.assignee_id = claimant_id
    task.claimed_at = utc_now()
    task.status = WORKBENCH_TASK_STATUS_PENDING_COMPLETION
    await session.flush()
    await session.refresh(task, attribute_names=["updated_at"])
    return task


async def submit_workbench_task_completion(
    session: AsyncSession,
    *,
    task_id: int,
    submitter_id: int,
    submission_content: str,
) -> WorkbenchTask:
    """执行人提交任务完成材料，任务进入待审核。"""

    await _get_user_or_404(session, user_id=submitter_id)
    repository = WorkbenchTaskRepository(session)
    task = await _get_task_or_404(repository, task_id=task_id, for_update=True)
    if task.assignee_id != submitter_id:
        raise AppError("WORKBENCH_TASK_ASSIGNEE_ONLY", "只有任务执行人可以提交完成材料", status_code=403)
    if task.status not in {WORKBENCH_TASK_STATUS_PENDING_COMPLETION, WORKBENCH_TASK_STATUS_REJECTED}:
        raise AppError("WORKBENCH_TASK_NOT_SUBMITTABLE", "任务当前不能提交完成材料", status_code=409)

    task.submission_content = normalize_required_text(
        submission_content,
        field_label="完成材料",
        max_length=2000,
    )
    task.submitted_at = utc_now()
    task.status = WORKBENCH_TASK_STATUS_PENDING_REVIEW
    await session.flush()
    await session.refresh(task, attribute_names=["updated_at"])
    return task


async def review_workbench_task(
    session: AsyncSession,
    *,
    task_id: int,
    reviewer_id: int,
    action: str,
    review_comment: str | None = None,
) -> WorkbenchTask:
    """
    发布人审核任务完成结果。

    审核通过后按任务引用的积分规则发放积分；如果规则已经撤回，任务进入
    `rule_revoked_pending`，由发布人或规则审批人按需求重新处理，不自动发分。
    """

    await _get_user_or_404(session, user_id=reviewer_id)
    repository = WorkbenchTaskRepository(session)
    task = await _get_task_or_404(repository, task_id=task_id, for_update=True)
    if task.publisher_id != reviewer_id:
        raise AppError("WORKBENCH_TASK_PUBLISHER_ONLY", "只有任务发布人可以审核任务", status_code=403)
    if task.status == WORKBENCH_TASK_STATUS_COMPLETED:
        return task
    if task.status != WORKBENCH_TASK_STATUS_PENDING_REVIEW:
        raise AppError("WORKBENCH_TASK_NOT_REVIEWABLE", "任务当前不在待审核状态", status_code=409)

    normalized_action = normalize_review_action(action)
    task.review_comment = normalize_optional_text(
        review_comment,
        field_label="审核意见",
        max_length=1000,
    )
    task.reviewed_by = reviewer_id
    task.reviewed_at = utc_now()
    if normalized_action == WORKBENCH_TASK_REVIEW_REJECT:
        task.status = WORKBENCH_TASK_STATUS_REJECTED
        await session.flush()
        await session.refresh(task, attribute_names=["updated_at"])
        return task

    if task.point_rule.status != POINT_RULE_STATUS_ACTIVE:
        task.status = WORKBENCH_TASK_STATUS_RULE_REVOKED_PENDING
        await session.flush()
        await session.refresh(task, attribute_names=["updated_at"])
        return task

    if task.assignee_id is None:
        raise AppError("WORKBENCH_TASK_ASSIGNEE_MISSING", "任务缺少执行人，不能审核通过", status_code=409)

    result = await grant_points_by_rule(
        session,
        rule_id=task.point_rule_id,
        user_id=task.assignee_id,
        operator_id=reviewer_id,
        idempotency_key=f"workbench-task:{task.id}:completion",
        business_id=str(task.id),
        reason=f"工作台任务完成：{task.title}",
    )
    task.point_ledger_entry_id = result.ledger_entry.id
    task.point_ledger_entry = result.ledger_entry
    task.status = WORKBENCH_TASK_STATUS_COMPLETED
    task.completed_at = utc_now()
    await session.flush()
    await session.refresh(task, attribute_names=["updated_at"])
    return task


# --- 内部查询与校验工具 ---
async def _get_task_or_404(
    repository: WorkbenchTaskRepository,
    *,
    task_id: int,
    for_update: bool = False,
) -> WorkbenchTask:
    """读取任务，不存在时抛出业务错误。"""

    task = await repository.get_task_by_id(task_id, for_update=for_update)
    if task is None:
        raise AppError("WORKBENCH_TASK_NOT_FOUND", "任务不存在", status_code=404)
    return task


async def _get_user_or_404(session: AsyncSession, *, user_id: int) -> User:
    """读取用户主体，不存在时抛出业务错误。"""

    repository = IdentityRepository(session)
    user = await repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)
    if user.status != "active":
        raise AppError("USER_DISABLED", "用户已被禁用", status_code=403)
    return user


async def _ensure_department_exists(session: AsyncSession, *, department_id: int) -> None:
    """确认任务关联部门存在且启用。"""

    department = await session.scalar(
        select(Department).where(Department.id == department_id, Department.status == "active"),
    )
    if department is None:
        raise AppError("DEPARTMENT_NOT_FOUND", "部门不存在或未启用", status_code=404)


def _ensure_different_active_user(*, publisher: User, assignee: User) -> None:
    """避免发布人把指定任务派给自己。"""

    if publisher.id == assignee.id:
        raise AppError("WORKBENCH_TASK_ASSIGN_SELF_FORBIDDEN", "任务发布人不能把任务派给自己", status_code=409)
