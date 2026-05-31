# app/interfaces/http/v1/borrowing/router.py
"""
借用 V1 路由

第一阶段开放物资借用申请、审批、取消和归还。接口路径使用通用 applications，
但 `borrow_type` 当前只接受 material，后续场地和工位复用同一生命周期继续扩展。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import AppError
from app.core.permissions.service import check_user_permission
from app.core.security.middleware import get_client_ip
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.borrowing.schemas import (
    BorrowApplicantCurrentContactResponse,
    BorrowApplicantSnapshotResponse,
    BorrowApplicantSummaryResponse,
    BorrowApplicationCancelRequest,
    BorrowApplicationCreateRequest,
    BorrowApplicationListItemResponse,
    BorrowApplicationPageResponse,
    BorrowApplicationResponse,
    BorrowApplicationReturnRequest,
    BorrowApplicationReviewRequest,
    BorrowApplicationUpdateRequest,
    BorrowItemResponse,
    BorrowReturnResponse,
    BorrowReviewResponse,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.borrowing.constants import BORROW_TYPE_MATERIAL
from app.modules.borrowing.materials import (
    cancel_material_borrow_application,
    create_material_borrow_application,
    get_applicant_current_contact,
    get_material_borrow_application,
    list_material_borrow_applications,
    return_material_borrow_application,
    review_material_borrow_application,
    update_material_borrow_application,
)
from app.modules.borrowing.models import BorrowApplication, BorrowItem, BorrowReturn, BorrowReview
from app.shared.request_context import get_request_id
from app.shared.responses import success_response
from app.shared.time import ensure_optional_utc_datetime, ensure_utc_datetime

router = APIRouter()


# --- 响应转换 ---
def build_borrow_item_response(item: BorrowItem) -> BorrowItemResponse:
    """把借用明细 ORM 对象转换成接口响应。"""

    return BorrowItemResponse(
        id=item.id,
        resource_type=item.resource_type,
        material_id=item.material_id,
        material_name=item.material_name_snapshot,
        category_name=item.category_name_snapshot,
        quantity=item.quantity,
        unit_deposit_points=item.unit_deposit_points_snapshot,
        subtotal_deposit_points=item.unit_deposit_points_snapshot * item.quantity,
    )


def build_borrow_applicant_snapshot_response(application: BorrowApplication) -> BorrowApplicantSnapshotResponse:
    """把申请人历史快照转换成接口响应。"""

    return BorrowApplicantSnapshotResponse(
        name=application.applicant_name_snapshot,
        student_id=application.applicant_student_id_snapshot,
        phone=application.applicant_phone_snapshot,
        email=application.applicant_email_snapshot,
        grade=application.applicant_grade_snapshot,
        major=application.applicant_major_snapshot,
    )


def build_borrow_applicant_summary_response(application: BorrowApplication) -> BorrowApplicantSummaryResponse:
    """把申请人历史快照转换成列表摘要。"""

    return BorrowApplicantSummaryResponse(
        name=application.applicant_name_snapshot,
        grade=application.applicant_grade_snapshot,
        major=application.applicant_major_snapshot,
    )


def build_material_summary(application: BorrowApplication) -> str:
    """根据借用明细快照生成列表物资摘要。"""

    items = sorted(application.items, key=lambda item: item.id)
    if not items:
        return ""
    first_item = items[0]
    first_summary = f"{first_item.material_name_snapshot} x {first_item.quantity}"
    if len(items) == 1:
        return first_summary
    return f"{first_summary} 等 {len(items)} 项"


def build_borrow_application_list_item_response(application: BorrowApplication) -> BorrowApplicationListItemResponse:
    """把借用申请转换成列表摘要响应。"""

    return BorrowApplicationListItemResponse(
        id=application.id,
        applicant_summary=build_borrow_applicant_summary_response(application),
        borrow_type=application.borrow_type,
        usage_type=application.usage_type,
        project_id=application.project_id,
        expected_return_at=ensure_utc_datetime(application.expected_return_at),
        status=application.status,
        deposit_points=application.deposit_points,
        submitted_at=ensure_utc_datetime(application.submitted_at),
        material_summary=build_material_summary(application),
        created_at=ensure_utc_datetime(application.created_at),
        updated_at=ensure_utc_datetime(application.updated_at),
    )


def build_borrow_review_response(review: BorrowReview) -> BorrowReviewResponse:
    """把借用审核记录 ORM 对象转换成接口响应。"""

    return BorrowReviewResponse(
        id=review.id,
        reviewer_id=review.reviewer_id,
        decision=review.decision,
        comment=review.comment,
        reviewed_at=ensure_utc_datetime(review.reviewed_at),
    )


def build_borrow_return_response(borrow_return: BorrowReturn) -> BorrowReturnResponse:
    """把借用归还记录 ORM 对象转换成接口响应。"""

    return BorrowReturnResponse(
        id=borrow_return.id,
        operator_id=borrow_return.operator_id,
        returned_at=ensure_utc_datetime(borrow_return.returned_at),
        condition=borrow_return.condition,
        comment=borrow_return.comment,
        point_action=borrow_return.point_action,
    )


def build_borrow_application_response(
    application: BorrowApplication,
    *,
    applicant_current_contact: dict[str, str | None] | None = None,
) -> BorrowApplicationResponse:
    """把借用申请 ORM 对象转换成接口响应。"""

    return BorrowApplicationResponse(
        id=application.id,
        applicant_id=application.applicant_id,
        applicant_snapshot=build_borrow_applicant_snapshot_response(application),
        applicant_current_contact=(
            BorrowApplicantCurrentContactResponse(**applicant_current_contact)
            if applicant_current_contact is not None
            else None
        ),
        borrow_type=application.borrow_type,
        usage_type=application.usage_type,
        project_id=application.project_id,
        reason=application.reason,
        expected_return_at=ensure_utc_datetime(application.expected_return_at),
        status=application.status,
        deposit_points=application.deposit_points,
        point_hold_id=application.point_hold_id,
        submitted_at=ensure_utc_datetime(application.submitted_at),
        cancelled_at=ensure_optional_utc_datetime(application.cancelled_at),
        cancel_reason=application.cancel_reason,
        items=[build_borrow_item_response(item) for item in application.items],
        reviews=[build_borrow_review_response(item) for item in application.reviews],
        returns=[build_borrow_return_response(item) for item in application.returns],
        created_at=ensure_utc_datetime(application.created_at),
        updated_at=ensure_utc_datetime(application.updated_at),
    )


def build_borrow_application_snapshot(application: BorrowApplication) -> dict:
    """构造审计日志使用的借用申请快照。"""

    return build_borrow_application_response(application).model_dump(mode="json")


# --- 借用申请 ---
@router.post("/borrowing/applications")
async def create_borrow_application(
    payload: BorrowApplicationCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """提交借用申请。"""

    if payload.borrow_type != BORROW_TYPE_MATERIAL:
        raise AppError("BORROW_TYPE_UNSUPPORTED", "第一阶段只支持物资借用", status_code=422)
    application = await create_material_borrow_application(
        session,
        applicant_id=current_user.user.id,
        usage_type=payload.usage_type,
        project_id=payload.project_id,
        reason=payload.reason,
        expected_return_at=payload.expected_return_at,
        items=[item.model_dump() for item in payload.items],
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="borrowing.application.create",
            target_type="borrow_application",
            target_id=str(application.id),
            after_snapshot=build_borrow_application_snapshot(application),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_borrow_application_response(application)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.patch("/borrowing/applications/{application_id}")
async def update_borrow_application(
    application_id: int,
    payload: BorrowApplicationUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """修改自己的待审核或已驳回借用申请。"""

    before = await get_material_borrow_application(
        session,
        application_id=application_id,
        viewer_id=current_user.user.id,
        can_view_all=False,
    )
    before_snapshot = build_borrow_application_snapshot(before)
    application = await update_material_borrow_application(
        session,
        application_id=application_id,
        applicant_id=current_user.user.id,
        reason=payload.reason,
        expected_return_at=payload.expected_return_at,
        items=[item.model_dump() for item in payload.items],
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="borrowing.application.update",
            target_type="borrow_application",
            target_id=str(application.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_borrow_application_snapshot(application),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_borrow_application_response(application)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/borrowing/applications")
async def get_borrow_applications(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    mine: bool = Query(default=False),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查询借用申请。"""

    decision = await check_user_permission(
        session,
        user_id=current_user.user.id,
        permission_code="borrowing.application.review",
    )
    page_data = await list_material_borrow_applications(
        session,
        viewer_id=current_user.user.id,
        can_view_all=decision.allowed,
        mine=mine,
        page=page,
        page_size=page_size,
        status=status,
    )
    data = BorrowApplicationPageResponse(
        items=[build_borrow_application_list_item_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/borrowing/applications/{application_id}")
async def get_borrow_application(
    application_id: int,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """读取借用申请详情。"""

    decision = await check_user_permission(
        session,
        user_id=current_user.user.id,
        permission_code="borrowing.application.review",
    )
    application = await get_material_borrow_application(
        session,
        application_id=application_id,
        viewer_id=current_user.user.id,
        can_view_all=decision.allowed,
    )
    current_contact = await get_applicant_current_contact(session, applicant_id=application.applicant_id)
    data = build_borrow_application_response(application, applicant_current_contact=current_contact)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/borrowing/applications/{application_id}/cancel")
async def cancel_borrow_application(
    application_id: int,
    payload: BorrowApplicationCancelRequest,
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """取消自己的借用申请。"""

    before = await get_material_borrow_application(
        session,
        application_id=application_id,
        viewer_id=current_user.user.id,
        can_view_all=False,
    )
    before_snapshot = build_borrow_application_snapshot(before)
    application = await cancel_material_borrow_application(
        session,
        application_id=application_id,
        applicant_id=current_user.user.id,
        cancel_reason=payload.cancel_reason,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="borrowing.application.cancel",
            target_type="borrow_application",
            target_id=str(application.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_borrow_application_snapshot(application),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.cancel_reason,
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_borrow_application_response(application)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/borrowing/applications/{application_id}/review")
async def review_borrow_application(
    application_id: int,
    payload: BorrowApplicationReviewRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("borrowing.application.review")),
    session: AsyncSession = Depends(get_session),
):
    """审核借用申请。"""

    before = await get_material_borrow_application(
        session,
        application_id=application_id,
        viewer_id=current_user.user.id,
        can_view_all=True,
    )
    before_snapshot = build_borrow_application_snapshot(before)
    application = await review_material_borrow_application(
        session,
        application_id=application_id,
        reviewer_id=current_user.user.id,
        decision=payload.decision,
        comment=payload.comment,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="borrowing.application.review",
            target_type="borrow_application",
            target_id=str(application.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_borrow_application_snapshot(application),
            extra={"decision": payload.decision},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.comment,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_borrow_application_response(application)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/borrowing/applications/{application_id}/return")
async def return_borrow_application(
    application_id: int,
    payload: BorrowApplicationReturnRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("borrowing.application.review")),
    session: AsyncSession = Depends(get_session),
):
    """确认借用归还。"""

    before = await get_material_borrow_application(
        session,
        application_id=application_id,
        viewer_id=current_user.user.id,
        can_view_all=True,
    )
    before_snapshot = build_borrow_application_snapshot(before)
    application = await return_material_borrow_application(
        session,
        application_id=application_id,
        operator_id=current_user.user.id,
        condition=payload.condition,
        comment=payload.comment,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="borrowing.application.return",
            target_type="borrow_application",
            target_id=str(application.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_borrow_application_snapshot(application),
            extra={"condition": payload.condition},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.comment,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_borrow_application_response(application)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))
