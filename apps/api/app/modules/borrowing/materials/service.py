# app/modules/borrowing/materials/service.py
"""
物资借用服务

本文件实现物资借用的申请、审批、取消和归还闭环。它参考旧后端“提交申请不扣库存、
审批通过扣库存、确认归还恢复库存”的业务语义，同时把押金冻结接入积分账本。
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.borrowing.constants import (
    BORROW_POINT_BUSINESS_TYPE,
    BORROW_RETURN_CONDITION_NORMAL,
    BORROW_RETURN_EXCEPTION_CONDITIONS,
    BORROW_REVIEW_APPROVE,
    BORROW_REVIEW_REJECT,
    BORROW_STATUS_APPROVED,
    BORROW_STATUS_CANCELLED,
    BORROW_STATUS_EXCEPTION_CLOSED,
    BORROW_STATUS_PENDING_REVIEW,
    BORROW_STATUS_REJECTED,
    BORROW_STATUS_RETURNED,
    BORROW_TYPE_MATERIAL,
    BORROW_USAGE_PERSONAL,
    BORROW_USAGE_PROJECT,
)
from app.modules.borrowing.materials.repository import MaterialBorrowRepository
from app.modules.borrowing.models import BorrowApplication, BorrowItem, BorrowReturn, BorrowReview
from app.modules.borrowing.types import BorrowApplicationPage
from app.modules.borrowing.utils import (
    normalize_optional_text,
    normalize_positive_quantity,
    normalize_required_text,
    normalize_return_condition,
    normalize_review_decision,
    normalize_usage_type,
)
from app.modules.identity.models import User
from app.modules.identity.repositories import IdentityRepository
from app.modules.organization.members.repository import MemberRepository
from app.modules.organization.models import MemberProfile
from app.modules.organization.utils import normalize_contact_email
from app.modules.points.accounts import get_or_create_point_account
from app.modules.points.holds import deduct_point_hold, freeze_points, release_point_hold
from app.modules.points.utils import ensure_available_balance
from app.modules.resources.constants import MATERIAL_STATUS_AVAILABLE, RESOURCE_TYPE_MATERIAL
from app.modules.resources.materials.repository import MaterialRepository
from app.modules.resources.models import Material
from app.shared.time import utc_now


class ApplicantSnapshot(TypedDict):
    """提交借用时固化的申请人资料。"""

    name: str
    student_id: str
    phone: str
    email: str
    grade: str
    major: str


class ApplicantCurrentContact(TypedDict):
    """后台详情辅助展示的当前联系方式。"""

    phone: str | None
    email: str | None


class NormalizedMaterialBorrowItem(TypedDict):
    """规范化后的物资借用明细。"""

    material_id: int
    quantity: int
    material_name: str
    category_name: str | None
    unit_deposit_points: int
    deposit_points: int


# --- 申请查询与提交 ---
async def list_material_borrow_applications(
    session: AsyncSession,
    *,
    viewer_id: int,
    can_view_all: bool = False,
    mine: bool = False,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
) -> BorrowApplicationPage:
    """分页查询物资借用申请。"""

    await _get_user_or_404(session, user_id=viewer_id)
    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    normalized_status = normalize_optional_text(status, field_label="申请状态", max_length=40)
    applicant_id = viewer_id if mine or not can_view_all else None

    repository = MaterialBorrowRepository(session)
    items, total = await repository.list_applications(
        page=normalized_page,
        page_size=normalized_page_size,
        applicant_id=applicant_id,
        status=normalized_status,
    )
    return BorrowApplicationPage(items=items, page=normalized_page, page_size=normalized_page_size, total=total)


async def get_material_borrow_application(
    session: AsyncSession,
    *,
    application_id: int,
    viewer_id: int,
    can_view_all: bool = False,
) -> BorrowApplication:
    """读取单条物资借用申请。"""

    await _get_user_or_404(session, user_id=viewer_id)
    repository = MaterialBorrowRepository(session)
    application = await _get_application_or_404(repository, application_id=application_id)
    if application.applicant_id != viewer_id and not can_view_all:
        raise AppError("BORROW_APPLICATION_FORBIDDEN", "只能查看自己的借用申请", status_code=403)
    return application


async def create_material_borrow_application(
    session: AsyncSession,
    *,
    applicant_id: int,
    items: list[dict[str, int]],
    reason: str,
    usage_type: str = BORROW_USAGE_PERSONAL,
    project_id: int | None = None,
    expected_return_at: datetime | None = None,
) -> BorrowApplication:
    """
    提交物资借用申请。

    提交时校验物资存在、状态可借、数量为正，并确认当前可用积分足以覆盖预计押金；
    但不扣库存、不冻结押金。库存和押金在审批通过时同一事务处理，避免申请堆积导致
    账面库存或积分被提前占用。
    """

    applicant = await _get_user_or_404(session, user_id=applicant_id)
    normalized_usage_type = normalize_usage_type(usage_type)
    if normalized_usage_type == BORROW_USAGE_PROJECT:
        raise AppError("BORROW_PROJECT_NOT_READY", "项目借用需要项目模块落地后开放", status_code=409)
    if project_id is not None:
        raise AppError("BORROW_PROJECT_FORBIDDEN", "个人借用不能携带项目 ID", status_code=422)

    normalized_reason = normalize_required_text(reason, field_label="借用理由", max_length=2000)
    if expected_return_at is None:
        raise AppError("BORROW_FIELD_REQUIRED", "预计归还时间不能为空", status_code=422)
    applicant_snapshot = await _build_applicant_snapshot(session, applicant)
    normalized_items = await _normalize_material_borrow_items(session, items=items)
    deposit_points = sum(item["deposit_points"] for item in normalized_items)
    await _ensure_deposit_available(session, user_id=applicant.id, deposit_points=deposit_points)

    application = BorrowApplication(
        applicant_id=applicant.id,
        applicant_name_snapshot=applicant_snapshot["name"],
        applicant_student_id_snapshot=applicant_snapshot["student_id"],
        applicant_phone_snapshot=applicant_snapshot["phone"],
        applicant_email_snapshot=applicant_snapshot["email"],
        applicant_grade_snapshot=applicant_snapshot["grade"],
        applicant_major_snapshot=applicant_snapshot["major"],
        borrow_type=BORROW_TYPE_MATERIAL,
        usage_type=normalized_usage_type,
        project_id=project_id,
        reason=normalized_reason,
        expected_return_at=expected_return_at,
        status=BORROW_STATUS_PENDING_REVIEW,
        deposit_points=deposit_points,
        submitted_at=utc_now(),
        items=[
            BorrowItem(
                resource_type=RESOURCE_TYPE_MATERIAL,
                material_id=item["material_id"],
                material_name_snapshot=item["material_name"],
                category_name_snapshot=item["category_name"],
                unit_deposit_points_snapshot=item["unit_deposit_points"],
                quantity=item["quantity"],
            )
            for item in normalized_items
        ],
    )
    repository = MaterialBorrowRepository(session)
    return await repository.add_application(application)


async def get_applicant_current_contact(
    session: AsyncSession,
    *,
    applicant_id: int,
) -> ApplicantCurrentContact:
    """读取申请人的当前联系方式，仅用于后台人工联系的辅助展示。"""

    user = await _get_user_or_404(session, user_id=applicant_id)
    member_repository = MemberRepository(session)
    profile = await member_repository.get_member_profile_by_user_id(applicant_id)
    return {
        "phone": _normalize_snapshot_optional_text(profile.phone if profile is not None else None),
        "email": _resolve_contact_email(profile=profile, user=user, strict=False),
    }


# --- 审批、取消与归还 ---
async def review_material_borrow_application(
    session: AsyncSession,
    *,
    application_id: int,
    reviewer_id: int,
    decision: str,
    comment: str | None = None,
) -> BorrowApplication:
    """
    审核物资借用申请。

    审批通过时先再次确认押金余额，再锁定申请和物资库存；若余额或库存不足，系统把本次
    审核落为驳回，并写明原因，不产生库存扣减和押金冻结。这样旧系统“库存不足自动拒绝”
    的语义被保留，同时避免审核等待期间积分变化造成半截状态。
    """

    await _get_user_or_404(session, user_id=reviewer_id)
    repository = MaterialBorrowRepository(session)
    application = await _get_application_or_404(repository, application_id=application_id, for_update=True)
    if application.borrow_type != BORROW_TYPE_MATERIAL:
        raise AppError("BORROW_TYPE_UNSUPPORTED", "当前只支持物资借用审核", status_code=422)
    if application.status != BORROW_STATUS_PENDING_REVIEW:
        raise AppError("BORROW_APPLICATION_NOT_REVIEWABLE", "申请当前不在待审核状态", status_code=409)

    normalized_decision = normalize_review_decision(decision)
    if normalized_decision == BORROW_REVIEW_REJECT:
        normalized_comment = normalize_required_text(comment, field_label="驳回理由", max_length=1000)
        application.status = BORROW_STATUS_REJECTED
        await repository.add_review(
            BorrowReview(
                application_id=application.id,
                reviewer_id=reviewer_id,
                decision=BORROW_REVIEW_REJECT,
                comment=normalized_comment,
                reviewed_at=utc_now(),
            ),
        )
        return await _refresh_application(repository, application.id)

    normalized_comment = normalize_optional_text(comment, field_label="审核意见", max_length=1000)
    deposit_shortage_message = await _get_deposit_shortage_message(
        session,
        user_id=application.applicant_id,
        deposit_points=application.deposit_points,
    )
    if deposit_shortage_message is not None:
        application.status = BORROW_STATUS_REJECTED
        await repository.add_review(
            BorrowReview(
                application_id=application.id,
                reviewer_id=reviewer_id,
                decision=BORROW_REVIEW_REJECT,
                comment=deposit_shortage_message,
                reviewed_at=utc_now(),
            ),
        )
        return await _refresh_application(repository, application.id)

    shortage_message = await _deduct_material_inventory_for_application(session, application=application)
    if shortage_message is not None:
        application.status = BORROW_STATUS_REJECTED
        await repository.add_review(
            BorrowReview(
                application_id=application.id,
                reviewer_id=reviewer_id,
                decision=BORROW_REVIEW_REJECT,
                comment=shortage_message,
                reviewed_at=utc_now(),
            ),
        )
        return await _refresh_application(repository, application.id)

    if application.deposit_points > 0:
        result = await freeze_points(
            session,
            user_id=application.applicant_id,
            amount=application.deposit_points,
            business_type=BORROW_POINT_BUSINESS_TYPE,
            business_id=str(application.id),
            idempotency_key=f"borrow-application:{application.id}:deposit-freeze",
            reason=f"物资借用押金冻结：申请 #{application.id}",
            operator_id=reviewer_id,
        )
        application.point_hold_id = result.hold.id if result.hold is not None else application.point_hold_id

    application.status = BORROW_STATUS_APPROVED
    await repository.add_review(
        BorrowReview(
            application_id=application.id,
            reviewer_id=reviewer_id,
            decision=BORROW_REVIEW_APPROVE,
            comment=normalized_comment,
            reviewed_at=utc_now(),
        ),
    )
    return await _refresh_application(repository, application.id)


async def _ensure_deposit_available(
    session: AsyncSession,
    *,
    user_id: int,
    deposit_points: int,
) -> None:
    """确认提交申请时的可用积分足以覆盖预计押金。"""

    if deposit_points <= 0:
        return

    account = await get_or_create_point_account(session, user_id=user_id, for_update=True)
    try:
        ensure_available_balance(account, deposit_points)
    except AppError as exc:
        if exc.code != "POINT_BALANCE_NOT_ENOUGH":
            raise
        raise AppError(
            "BORROW_DEPOSIT_NOT_ENOUGH",
            f"可用积分不足，预计需要冻结 {deposit_points} 积分。",
            status_code=409,
            details={
                "required_deposit_points": deposit_points,
                "available_points": account.available_balance,
            },
        ) from exc


async def _get_deposit_shortage_message(
    session: AsyncSession,
    *,
    user_id: int,
    deposit_points: int,
) -> str | None:
    """审核时返回押金余额不足的自动驳回原因。"""

    if deposit_points <= 0:
        return None

    account = await get_or_create_point_account(session, user_id=user_id, for_update=True)
    try:
        ensure_available_balance(account, deposit_points)
    except AppError as exc:
        if exc.code != "POINT_BALANCE_NOT_ENOUGH":
            raise
        return (
            "积分余额不足，系统自动驳回："
            f"当前可用 {account.available_balance}，预计需要冻结 {deposit_points}。"
        )
    return None


async def cancel_material_borrow_application(
    session: AsyncSession,
    *,
    application_id: int,
    applicant_id: int,
    cancel_reason: str | None = None,
) -> BorrowApplication:
    """
    取消自己的物资借用申请。

    第一阶段允许申请人取消待审核或已驳回申请。取消已驳回申请只是用户侧收尾，
    不删除审核记录，也不撤销管理员的驳回结论。
    """

    await _get_user_or_404(session, user_id=applicant_id)
    repository = MaterialBorrowRepository(session)
    application = await _get_application_or_404(repository, application_id=application_id, for_update=True)
    if application.applicant_id != applicant_id:
        raise AppError("BORROW_APPLICATION_OWNER_ONLY", "只能取消自己的借用申请", status_code=403)
    if application.status not in {BORROW_STATUS_PENDING_REVIEW, BORROW_STATUS_REJECTED}:
        raise AppError("BORROW_APPLICATION_NOT_CANCELLABLE", "申请当前不能取消", status_code=409)

    application.status = BORROW_STATUS_CANCELLED
    application.cancelled_at = utc_now()
    application.cancel_reason = normalize_optional_text(cancel_reason, field_label="取消原因", max_length=1000)
    await session.flush()
    return await _refresh_application(repository, application.id)


async def return_material_borrow_application(
    session: AsyncSession,
    *,
    application_id: int,
    operator_id: int,
    condition: str = BORROW_RETURN_CONDITION_NORMAL,
    comment: str | None = None,
) -> BorrowApplication:
    """
    确认物资归还。

    正常归还恢复库存并解冻押金；第一阶段损坏、遗失或消耗类归还不自动恢复可借库存，
    并全额扣除本次申请冻结押金。异常关闭后不提供业务撤销流程，误操作只能通过受控
    库存调整和积分反向修正兜底；专门撤销流程留到后续增量。
    """

    await _get_user_or_404(session, user_id=operator_id)
    repository = MaterialBorrowRepository(session)
    application = await _get_application_or_404(repository, application_id=application_id, for_update=True)
    if application.status != BORROW_STATUS_APPROVED:
        raise AppError("BORROW_APPLICATION_NOT_RETURNABLE", "申请当前不能确认归还", status_code=409)

    normalized_condition = normalize_return_condition(condition)
    if normalized_condition in BORROW_RETURN_EXCEPTION_CONDITIONS:
        normalized_comment = normalize_required_text(comment, field_label="异常归还备注", max_length=1000)
    else:
        normalized_comment = normalize_optional_text(comment, field_label="归还备注", max_length=1000)
    if normalized_condition == BORROW_RETURN_CONDITION_NORMAL:
        await _restore_material_inventory_for_application(session, application=application)

    point_action: str | None = None
    if application.point_hold_id is not None:
        if normalized_condition == BORROW_RETURN_CONDITION_NORMAL:
            await release_point_hold(
                session,
                hold_id=application.point_hold_id,
                idempotency_key=f"borrow-application:{application.id}:deposit-release",
                reason=f"物资借用正常归还：申请 #{application.id}",
                operator_id=operator_id,
            )
            point_action = "release"
            application.status = BORROW_STATUS_RETURNED
        else:
            await deduct_point_hold(
                session,
                hold_id=application.point_hold_id,
                idempotency_key=f"borrow-application:{application.id}:deposit-deduct",
                reason=f"物资借用异常归还：申请 #{application.id}",
                operator_id=operator_id,
            )
            point_action = "deduct"
            application.status = BORROW_STATUS_EXCEPTION_CLOSED
    elif normalized_condition in BORROW_RETURN_EXCEPTION_CONDITIONS:
        application.status = BORROW_STATUS_EXCEPTION_CLOSED
    else:
        application.status = BORROW_STATUS_RETURNED

    await repository.add_return(
        BorrowReturn(
            application_id=application.id,
            operator_id=operator_id,
            returned_at=utc_now(),
            condition=normalized_condition,
            comment=normalized_comment,
            point_action=point_action,
        ),
    )
    return await _refresh_application(repository, application.id)


# --- 内部校验和跨域库存操作 ---
async def _normalize_material_borrow_items(
    session: AsyncSession,
    *,
    items: list[dict[str, int]],
) -> list[NormalizedMaterialBorrowItem]:
    """规范化申请物资明细，并合并重复物资。"""

    if not items:
        raise AppError("BORROW_ITEMS_REQUIRED", "物资借用至少需要一条明细", status_code=422)

    quantities: dict[int, int] = {}
    for item in items:
        material_id = item.get("material_id")
        if material_id is None:
            raise AppError("BORROW_ITEM_MATERIAL_REQUIRED", "物资明细必须包含 material_id", status_code=422)
        quantity = normalize_positive_quantity(item.get("quantity", 0), field_label="借用数量")
        quantities[material_id] = quantities.get(material_id, 0) + quantity

    material_repository = MaterialRepository(session)
    normalized_items: list[NormalizedMaterialBorrowItem] = []
    for material_id, quantity in quantities.items():
        material = await material_repository.get_material_by_id(material_id)
        _ensure_material_borrowable(material)
        unit_deposit_points = material.deposit_points if material is not None else 0
        normalized_items.append(
            {
                "material_id": material_id,
                "quantity": quantity,
                "material_name": material.name if material is not None else "",
                "category_name": (
                    material.category.name if material is not None and material.category is not None else None
                ),
                "unit_deposit_points": unit_deposit_points,
                "deposit_points": unit_deposit_points * quantity,
            },
        )
    return normalized_items


async def _deduct_material_inventory_for_application(
    session: AsyncSession,
    *,
    application: BorrowApplication,
) -> str | None:
    """审批通过时扣减申请明细对应的可借库存，库存不足时返回拒绝原因。"""

    material_repository = MaterialRepository(session)
    locked_materials: dict[int, Material] = {}
    for item in application.items:
        if item.material_id is None:
            return "借用明细缺少物资 ID，系统自动驳回。"
        material = await material_repository.get_material_by_id(item.material_id, for_update=True)
        try:
            _ensure_material_borrowable(material)
        except AppError as exc:
            return f"物资不可借用：{exc.message}"
        if material is None:
            return "物资不存在，系统自动驳回。"
        if material.available_quantity < item.quantity:
            return (
                f"物资库存不足：{item.material_name_snapshot} "
                f"当前可借 {material.available_quantity}，申请 {item.quantity}。"
            )
        locked_materials[item.material_id] = material

    for item in application.items:
        material = locked_materials[item.material_id]
        material.available_quantity -= item.quantity
    await session.flush()
    return None


async def _restore_material_inventory_for_application(
    session: AsyncSession,
    *,
    application: BorrowApplication,
) -> None:
    """归还时恢复申请明细对应的可借库存。"""

    material_repository = MaterialRepository(session)
    for item in application.items:
        if item.material_id is None:
            continue
        material = await material_repository.get_material_by_id(item.material_id, for_update=True)
        if material is None:
            raise AppError("MATERIAL_NOT_FOUND", "归还物资不存在，无法恢复库存", status_code=404)
        material.available_quantity = min(material.total_quantity, material.available_quantity + item.quantity)
    await session.flush()


def _ensure_material_borrowable(material: Material | None) -> None:
    """确认物资存在且当前允许借用。"""

    if material is None:
        raise AppError("MATERIAL_NOT_FOUND", "物资不存在", status_code=404)
    if material.status != MATERIAL_STATUS_AVAILABLE:
        raise AppError("MATERIAL_NOT_AVAILABLE", "物资当前不可借用", status_code=409)


async def _build_applicant_snapshot(session: AsyncSession, user: User) -> ApplicantSnapshot:
    """从成员资料和登录邮箱生成借用申请人快照。"""

    member_repository = MemberRepository(session)
    profile = await member_repository.get_member_profile_by_user_id(user.id)
    missing_fields: list[str] = []
    if profile is None:
        missing_fields.extend(["real_name", "student_id", "phone", "email", "grade", "major"])
        raise _build_profile_incomplete_error(missing_fields)

    name = _require_snapshot_text(profile.real_name, field="real_name", missing_fields=missing_fields)
    student_id = _require_snapshot_text(profile.student_id, field="student_id", missing_fields=missing_fields)
    phone = _require_snapshot_text(profile.phone, field="phone", missing_fields=missing_fields)
    grade = _require_snapshot_text(profile.grade, field="grade", missing_fields=missing_fields)
    major = _require_snapshot_text(profile.major, field="major", missing_fields=missing_fields)
    email = _resolve_contact_email(profile=profile, user=user, strict=True, missing_fields=missing_fields)

    if missing_fields:
        raise _build_profile_incomplete_error(missing_fields)
    return {
        "name": name,
        "student_id": student_id,
        "phone": phone,
        "email": email,
        "grade": grade,
        "major": major,
    }


def _require_snapshot_text(value: str | None, *, field: str, missing_fields: list[str]) -> str:
    """读取快照必填字段，缺失时记录字段名。"""

    normalized = _normalize_snapshot_optional_text(value)
    if normalized is None:
        missing_fields.append(field)
        return ""
    return normalized


def _normalize_snapshot_optional_text(value: str | None) -> str | None:
    """清理快照使用的可选文本。"""

    if value is None:
        return None
    normalized = value.strip()
    return normalized or None


def _resolve_contact_email(
    *,
    profile: MemberProfile | None,
    user: User,
    strict: bool,
    missing_fields: list[str] | None = None,
) -> str | None:
    """按成员资料联系邮箱优先、登录邮箱兜底的规则生成联系邮箱。"""

    profile_email = _normalize_snapshot_optional_text(profile.email if profile is not None else None)
    login_email = user.email_password_account.email if user.email_password_account is not None else None

    if profile_email is not None:
        try:
            return normalize_contact_email(profile_email)
        except AppError as exc:
            if exc.code != "MEMBER_PROFILE_EMAIL_INVALID" or not strict:
                if strict:
                    raise
                return None
            if missing_fields is not None:
                missing_fields.append("email")
            return None

    if login_email is not None:
        try:
            return normalize_contact_email(login_email)
        except AppError as exc:
            if exc.code != "MEMBER_PROFILE_EMAIL_INVALID" or not strict:
                if strict:
                    raise
                return None
            if missing_fields is not None:
                missing_fields.append("email")
            return None

    if strict and missing_fields is not None:
        missing_fields.append("email")
    return None


def _build_profile_incomplete_error(missing_fields: list[str]) -> AppError:
    """构生成员资料不完整错误。"""

    return AppError(
        "BORROW_PROFILE_INCOMPLETE",
        "成员资料不完整，请先完善姓名、学号、手机号、联系邮箱、年级和专业。",
        status_code=422,
        details={"missing_fields": missing_fields},
    )


async def _get_application_or_404(
    repository: MaterialBorrowRepository,
    *,
    application_id: int,
    for_update: bool = False,
) -> BorrowApplication:
    """读取借用申请，不存在时抛出业务错误。"""

    application = await repository.get_application_by_id(application_id, for_update=for_update)
    if application is None:
        raise AppError("BORROW_APPLICATION_NOT_FOUND", "借用申请不存在", status_code=404)
    return application


async def _refresh_application(
    repository: MaterialBorrowRepository,
    application_id: int,
) -> BorrowApplication:
    """重新读取包含明细、审核和归还记录的申请快照。"""

    refreshed = await repository.get_application_by_id(application_id)
    if refreshed is None:
        raise AppError("BORROW_APPLICATION_NOT_FOUND", "借用申请不存在", status_code=404)
    return refreshed


async def _get_user_or_404(session: AsyncSession, *, user_id: int) -> User:
    """读取用户主体，不存在或禁用时抛出业务错误。"""

    repository = IdentityRepository(session)
    user = await repository.get_user_by_id(user_id)
    if user is None:
        raise AppError("USER_NOT_FOUND", "用户不存在", status_code=404)
    if user.status != "active":
        raise AppError("USER_DISABLED", "用户已被禁用", status_code=403)
    return user
