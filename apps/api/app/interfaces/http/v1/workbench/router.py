# app/interfaces/http/v1/workbench/router.py
"""
工作台 V1 路由

当前先开放任务闭环：发布任务、查询任务、领取悬赏任务、提交完成材料和发布人审核。
排班和值班接口保留在文档规划中，等任务模型稳定后继续按二级能力模块接入。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security.middleware import get_client_ip
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.workbench.schemas import (
    WorkbenchTaskCreateRequest,
    WorkbenchTaskPageResponse,
    WorkbenchTaskResponse,
    WorkbenchTaskReviewRequest,
    WorkbenchTaskSubmitRequest,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.workbench.models import WorkbenchTask
from app.modules.workbench.tasks import (
    claim_workbench_task,
    list_workbench_tasks,
    publish_workbench_task,
    review_workbench_task,
    submit_workbench_task_completion,
)
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


# --- 响应转换 ---
def build_workbench_task_response(task: WorkbenchTask) -> WorkbenchTaskResponse:
    """把工作台任务 ORM 对象转换成接口响应。"""

    return WorkbenchTaskResponse(
        id=task.id,
        title=task.title,
        task_type=task.task_type,
        assignment_type=task.assignment_type,
        visibility=task.visibility,
        department_id=task.department_id,
        content=task.content,
        deadline=task.deadline,
        status=task.status,
        publisher_id=task.publisher_id,
        assignee_id=task.assignee_id,
        claimed_at=task.claimed_at,
        point_rule_id=task.point_rule_id,
        point_rule_amount=task.point_rule.amount if task.point_rule is not None else 0,
        submission_content=task.submission_content,
        submitted_at=task.submitted_at,
        reviewed_by=task.reviewed_by,
        reviewed_at=task.reviewed_at,
        review_comment=task.review_comment,
        completed_at=task.completed_at,
        point_ledger_entry_id=task.point_ledger_entry_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def build_task_snapshot(task: WorkbenchTask) -> dict:
    """构造审计日志使用的任务快照。"""

    return build_workbench_task_response(task).model_dump(mode="json")


# --- 任务接口 ---
@router.post("/workbench/tasks")
async def create_workbench_task(
    payload: WorkbenchTaskCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("workbench.task.publish")),
    session: AsyncSession = Depends(get_session),
):
    """发布工作台任务。"""

    task = await publish_workbench_task(
        session,
        publisher_id=current_user.user.id,
        title=payload.title,
        task_type=payload.task_type,
        assignment_type=payload.assignment_type,
        visibility=payload.visibility,
        department_id=payload.department_id,
        content=payload.content,
        deadline=payload.deadline,
        point_rule_id=payload.point_rule_id,
        assignee_id=payload.assignee_id,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="workbench.task.publish",
            target_type="workbench_task",
            target_id=str(task.id),
            after_snapshot=build_task_snapshot(task),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.content,
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_workbench_task_response(task)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/workbench/tasks")
async def get_workbench_tasks(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    mine: bool = Query(default=False),
    available_to_claim: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查询工作台任务。"""

    page_data = await list_workbench_tasks(
        session,
        viewer_id=current_user.user.id,
        page=page,
        page_size=page_size,
        status=status,
        mine=mine,
        available_to_claim=available_to_claim,
    )
    data = WorkbenchTaskPageResponse(
        items=[build_workbench_task_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/workbench/tasks/{task_id}/claim")
async def claim_task(
    task_id: int,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """领取悬赏任务。"""

    task = await claim_workbench_task(
        session,
        task_id=task_id,
        claimant_id=current_user.user.id,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="workbench.task.claim",
            target_type="workbench_task",
            target_id=str(task.id),
            after_snapshot=build_task_snapshot(task),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_workbench_task_response(task)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/workbench/tasks/{task_id}/submit")
async def submit_task_completion(
    task_id: int,
    payload: WorkbenchTaskSubmitRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """提交任务完成材料。"""

    task = await submit_workbench_task_completion(
        session,
        task_id=task_id,
        submitter_id=current_user.user.id,
        submission_content=payload.submission_content,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="workbench.task.submit",
            target_type="workbench_task",
            target_id=str(task.id),
            after_snapshot=build_task_snapshot(task),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.submission_content,
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_workbench_task_response(task)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/workbench/tasks/{task_id}/review")
async def review_task_completion(
    task_id: int,
    payload: WorkbenchTaskReviewRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """审核任务完成结果。"""

    task = await review_workbench_task(
        session,
        task_id=task_id,
        reviewer_id=current_user.user.id,
        action=payload.action,
        review_comment=payload.review_comment,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="workbench.task.review",
            target_type="workbench_task",
            target_id=str(task.id),
            after_snapshot=build_task_snapshot(task),
            extra={"review_action": payload.action},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.review_comment,
            risk_level="high" if task.status == "completed" else "medium",
        ),
    )
    await session.commit()
    data = build_workbench_task_response(task)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))
