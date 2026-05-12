# app/modules/points/rules/service.py
"""
积分规则服务

本文件负责固定规则维护、临时规则申请审批、撤回，以及按规则发放积分。这里的规则
服务只处理账本域自己的状态机；任务发布、任务领取、通知触达等后续由 workbench
等业务域引用规则模板后再完成。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.organization.models import Department
from app.modules.points.accounts import ensure_user_exists, get_or_create_point_account
from app.modules.points.constants import (
    POINT_DIRECTION_INCOME,
    POINT_RULE_STATUS_ACTIVE,
    POINT_RULE_STATUS_REVOKED,
    POINT_RULE_TYPE_FIXED,
    POINT_RULE_TYPE_TEMPORARY_TASK_TEMPLATE,
    TEMPORARY_POINT_RULE_APPROVAL_APPROVED,
    TEMPORARY_POINT_RULE_APPROVAL_PENDING,
    TEMPORARY_POINT_RULE_APPROVAL_REJECTED,
    TEMPORARY_POINT_RULE_EVENT_APPROVED,
    TEMPORARY_POINT_RULE_EVENT_REJECTED,
    TEMPORARY_POINT_RULE_EVENT_REVOKED,
    TEMPORARY_POINT_RULE_EVENT_SUBMITTED,
    TEMPORARY_POINT_RULE_REVOKE_ACTIVE,
    TEMPORARY_POINT_RULE_REVOKE_NONE,
    TEMPORARY_POINT_RULE_REVOKE_REVOKED,
)
from app.modules.points.ledger import append_ledger_entry, get_existing_idempotent_result
from app.modules.points.models import PointRule, TemporaryPointRule, TemporaryPointRuleEvent
from app.modules.points.rules.repository import PointRuleRepository
from app.modules.points.types import PointOperationResult
from app.modules.points.utils import (
    ensure_account_active,
    normalize_idempotency_key,
    normalize_optional_reason,
    normalize_positive_amount,
    normalize_required_label,
    normalize_required_reason,
)
from app.shared.time import utc_now


@dataclass(frozen=True)
class TemporaryPointRulePage:
    """临时积分规则申请分页结果。"""

    items: list[TemporaryPointRule]
    page: int
    page_size: int
    total: int


# --- 固定规则 ---
async def create_point_rule(
    session: AsyncSession,
    *,
    code: str,
    name: str,
    amount: int,
    operator_id: int,
    rule_type: str = POINT_RULE_TYPE_FIXED,
    description: str | None = None,
    effective_from: datetime | None = None,
    effective_to: datetime | None = None,
) -> PointRule:
    """
    创建积分规则。

    第一阶段只允许接口层创建固定规则；临时任务模板必须由临时规则审批流程生成，避免
    任务发布人绕过审批直接创建一次性高额积分任务。
    """

    normalized_code = normalize_required_label(code, field_label="积分规则 code", max_length=64)
    normalized_name = normalize_required_label(name, field_label="积分规则名称", max_length=120)
    normalized_amount = normalize_positive_amount(amount)
    normalized_description = normalize_optional_reason(description)
    normalized_rule_type = normalize_required_label(rule_type, field_label="积分规则类型", max_length=40)
    if normalized_rule_type != POINT_RULE_TYPE_FIXED:
        raise AppError("POINT_RULE_TYPE_UNSUPPORTED", "接口层只能直接创建固定积分规则", status_code=422)
    _ensure_effective_window(effective_from=effective_from, effective_to=effective_to)
    await ensure_user_exists(session, user_id=operator_id)

    repository = PointRuleRepository(session)
    existing = await repository.get_point_rule_by_code(normalized_code)
    if existing is not None:
        raise AppError("POINT_RULE_CODE_EXISTS", "积分规则 code 已存在", status_code=409)

    rule = PointRule(
        code=normalized_code,
        name=normalized_name,
        rule_type=normalized_rule_type,
        status=POINT_RULE_STATUS_ACTIVE,
        version=1,
        amount=normalized_amount,
        description=normalized_description,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by=operator_id,
        updated_by=operator_id,
    )
    return await repository.add_point_rule(rule)


async def list_point_rules(
    session: AsyncSession,
    *,
    include_revoked: bool = False,
    rule_type: str | None = None,
) -> list[PointRule]:
    """列出积分规则。"""

    repository = PointRuleRepository(session)
    normalized_rule_type = rule_type.strip() if rule_type else None
    return await repository.list_point_rules(
        include_revoked=include_revoked,
        rule_type=normalized_rule_type,
    )


async def revoke_point_rule(
    session: AsyncSession,
    *,
    rule_id: int,
    reason: str,
    operator_id: int,
) -> PointRule:
    """
    撤回固定积分规则或一次性任务模板。

    撤回只停止规则后续使用，不处理已经产生的积分流水。确需追回时应调用
    `reverse_ledger_entry` 追加反向流水。
    """

    normalized_reason = normalize_required_reason(reason)
    await ensure_user_exists(session, user_id=operator_id)
    repository = PointRuleRepository(session)
    rule = await repository.get_point_rule_by_id(rule_id)
    if rule is None:
        raise AppError("POINT_RULE_NOT_FOUND", "积分规则不存在", status_code=404)
    if rule.status == POINT_RULE_STATUS_REVOKED:
        return rule

    rule.status = POINT_RULE_STATUS_REVOKED
    rule.description = _append_operation_note(rule.description, f"撤回原因：{normalized_reason}")
    rule.updated_by = operator_id
    now = _now_matching(rule.effective_to) if rule.effective_to is not None else utc_now()
    if rule.effective_to is None or rule.effective_to > now:
        rule.effective_to = now
    await session.flush()
    await session.refresh(rule)
    return rule


# --- 临时规则申请与审批 ---
async def submit_temporary_point_rule(
    session: AsyncSession,
    *,
    applicant_id: int,
    name: str,
    task_type: str,
    target_scope: str,
    reason: str,
    amount_per_completion: int,
    max_participants: int,
    total_points_limit: int,
    effective_from: datetime,
    effective_to: datetime,
    department_id: int | None = None,
    completion_requirements: str | None = None,
) -> TemporaryPointRule:
    """
    提交临时积分规则申请。

    该申请只表示“希望创建一个特殊非模板任务的积分规则”。审批通过之前不会生成
    可用积分规则，也不能被任务域引用。
    """

    await ensure_user_exists(session, user_id=applicant_id)
    if department_id is not None:
        await _ensure_department_exists(session, department_id=department_id)
    normalized_name = normalize_required_label(name, field_label="临时规则名称", max_length=120)
    normalized_task_type = normalize_required_label(task_type, field_label="任务类型", max_length=64)
    normalized_target_scope = normalize_required_label(target_scope, field_label="适用对象", max_length=64)
    normalized_reason = normalize_required_reason(reason)
    normalized_requirements = normalize_optional_reason(completion_requirements)
    normalized_amount = normalize_positive_amount(amount_per_completion)
    normalized_max_participants = normalize_positive_amount(max_participants)
    normalized_total_limit = normalize_positive_amount(total_points_limit)
    if normalized_total_limit < normalized_amount:
        raise AppError("POINT_RULE_TOTAL_LIMIT_TOO_SMALL", "总积分上限不能小于单次发放积分", status_code=422)
    if normalized_total_limit > normalized_amount * normalized_max_participants:
        raise AppError("POINT_RULE_TOTAL_LIMIT_INVALID", "总积分上限不能超过单次积分与人数上限乘积", status_code=422)
    _ensure_effective_window(effective_from=effective_from, effective_to=effective_to)

    repository = PointRuleRepository(session)
    rule = TemporaryPointRule(
        name=normalized_name,
        task_type=normalized_task_type,
        target_scope=normalized_target_scope,
        department_id=department_id,
        reason=normalized_reason,
        completion_requirements=normalized_requirements,
        amount_per_completion=normalized_amount,
        max_participants=normalized_max_participants,
        total_points_limit=normalized_total_limit,
        effective_from=effective_from,
        effective_to=effective_to,
        approval_status=TEMPORARY_POINT_RULE_APPROVAL_PENDING,
        applicant_id=applicant_id,
        revoke_status=TEMPORARY_POINT_RULE_REVOKE_NONE,
    )
    rule = await repository.add_temporary_rule(rule)
    await _record_temporary_rule_event(
        repository,
        rule_id=rule.id,
        event_type=TEMPORARY_POINT_RULE_EVENT_SUBMITTED,
        actor_id=applicant_id,
        reason=normalized_reason,
        extra={"amount_per_completion": normalized_amount, "total_points_limit": normalized_total_limit},
    )
    return rule


async def list_temporary_point_rules(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    approval_status: str | None = None,
) -> TemporaryPointRulePage:
    """分页列出临时积分规则申请。"""

    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    normalized_status = approval_status.strip() if approval_status else None
    repository = PointRuleRepository(session)
    items, total = await repository.list_temporary_rules(
        page=normalized_page,
        page_size=normalized_page_size,
        approval_status=normalized_status,
    )
    return TemporaryPointRulePage(
        items=items,
        page=normalized_page,
        page_size=normalized_page_size,
        total=total,
    )


async def approve_temporary_point_rule(
    session: AsyncSession,
    *,
    rule_id: int,
    approver_id: int,
    approval_reason: str,
) -> TemporaryPointRule:
    """
    审批通过临时积分规则，并生成一次性任务模板。

    生成的 `PointRule` 是后续任务域发布特殊任务时唯一可引用的积分模板；任务发布时
    不能再临时修改积分数、人数上限或有效期。
    """

    normalized_reason = normalize_required_reason(approval_reason)
    await ensure_user_exists(session, user_id=approver_id)
    repository = PointRuleRepository(session)
    temporary_rule = await _get_temporary_rule_or_404(repository, rule_id=rule_id)
    if temporary_rule.approval_status != TEMPORARY_POINT_RULE_APPROVAL_PENDING:
        raise AppError("TEMPORARY_POINT_RULE_NOT_PENDING", "临时积分规则不在待审批状态", status_code=409)

    point_rule = PointRule(
        code=f"temporary-rule-{temporary_rule.id}-v1",
        name=f"一次性任务模板：{temporary_rule.name}",
        rule_type=POINT_RULE_TYPE_TEMPORARY_TASK_TEMPLATE,
        status=POINT_RULE_STATUS_ACTIVE,
        version=1,
        amount=temporary_rule.amount_per_completion,
        description=f"由临时积分规则 #{temporary_rule.id} 审批生成。申请原因：{temporary_rule.reason}",
        effective_from=temporary_rule.effective_from,
        effective_to=temporary_rule.effective_to,
        created_by=approver_id,
        updated_by=approver_id,
    )
    point_rule = await repository.add_point_rule(point_rule)

    now = utc_now()
    temporary_rule.approval_status = TEMPORARY_POINT_RULE_APPROVAL_APPROVED
    temporary_rule.approved_by = approver_id
    temporary_rule.approved_at = now
    temporary_rule.approval_reason = normalized_reason
    temporary_rule.generated_point_rule_id = point_rule.id
    temporary_rule.generated_point_rule = point_rule
    temporary_rule.revoke_status = TEMPORARY_POINT_RULE_REVOKE_ACTIVE
    await _record_temporary_rule_event(
        repository,
        rule_id=temporary_rule.id,
        event_type=TEMPORARY_POINT_RULE_EVENT_APPROVED,
        actor_id=approver_id,
        reason=normalized_reason,
        extra={"generated_point_rule_id": point_rule.id},
    )
    await session.flush()
    await session.refresh(temporary_rule, attribute_names=["updated_at"])
    return temporary_rule


async def reject_temporary_point_rule(
    session: AsyncSession,
    *,
    rule_id: int,
    reviewer_id: int,
    rejection_reason: str,
) -> TemporaryPointRule:
    """驳回临时积分规则申请。"""

    normalized_reason = normalize_required_reason(rejection_reason)
    await ensure_user_exists(session, user_id=reviewer_id)
    repository = PointRuleRepository(session)
    temporary_rule = await _get_temporary_rule_or_404(repository, rule_id=rule_id)
    if temporary_rule.approval_status != TEMPORARY_POINT_RULE_APPROVAL_PENDING:
        raise AppError("TEMPORARY_POINT_RULE_NOT_PENDING", "临时积分规则不在待审批状态", status_code=409)

    temporary_rule.approval_status = TEMPORARY_POINT_RULE_APPROVAL_REJECTED
    temporary_rule.rejected_by = reviewer_id
    temporary_rule.rejected_at = utc_now()
    temporary_rule.rejection_reason = normalized_reason
    await _record_temporary_rule_event(
        repository,
        rule_id=temporary_rule.id,
        event_type=TEMPORARY_POINT_RULE_EVENT_REJECTED,
        actor_id=reviewer_id,
        reason=normalized_reason,
    )
    await session.flush()
    await session.refresh(temporary_rule, attribute_names=["updated_at"])
    return temporary_rule


async def revoke_temporary_point_rule(
    session: AsyncSession,
    *,
    rule_id: int,
    operator_id: int,
    revoke_reason: str,
    revoke_impact_note: str,
) -> TemporaryPointRule:
    """
    撤回已发布的临时积分规则。

    撤回默认只停止后续继续使用，不自动追回已经发放的积分。`revoke_impact_note`
    会作为通知和后续任务处理的占位数据保存下来。
    """

    normalized_reason = normalize_required_reason(revoke_reason)
    normalized_impact = normalize_required_reason(revoke_impact_note)
    await ensure_user_exists(session, user_id=operator_id)
    repository = PointRuleRepository(session)
    temporary_rule = await _get_temporary_rule_or_404(repository, rule_id=rule_id)
    if temporary_rule.approval_status != TEMPORARY_POINT_RULE_APPROVAL_APPROVED:
        raise AppError("TEMPORARY_POINT_RULE_NOT_APPROVED", "只有已审批通过的临时规则可以撤回", status_code=409)
    if temporary_rule.revoke_status == TEMPORARY_POINT_RULE_REVOKE_REVOKED:
        return temporary_rule

    temporary_rule.revoke_status = TEMPORARY_POINT_RULE_REVOKE_REVOKED
    temporary_rule.revoked_by = operator_id
    temporary_rule.revoked_at = utc_now()
    temporary_rule.revoke_reason = normalized_reason
    temporary_rule.revoke_impact_note = normalized_impact

    if temporary_rule.generated_point_rule is not None:
        temporary_rule.generated_point_rule.status = POINT_RULE_STATUS_REVOKED
        temporary_rule.generated_point_rule.updated_by = operator_id
        effective_revoke_time = (
            _now_matching(temporary_rule.generated_point_rule.effective_to)
            if temporary_rule.generated_point_rule.effective_to is not None
            else temporary_rule.revoked_at
        )
        if (
            temporary_rule.generated_point_rule.effective_to is None
            or temporary_rule.generated_point_rule.effective_to > effective_revoke_time
        ):
            temporary_rule.generated_point_rule.effective_to = effective_revoke_time

    await _record_temporary_rule_event(
        repository,
        rule_id=temporary_rule.id,
        event_type=TEMPORARY_POINT_RULE_EVENT_REVOKED,
        actor_id=operator_id,
        reason=normalized_reason,
        extra={"revoke_impact_note": normalized_impact},
    )
    await session.flush()
    await session.refresh(temporary_rule, attribute_names=["updated_at"])
    if temporary_rule.generated_point_rule is not None:
        await session.refresh(temporary_rule.generated_point_rule, attribute_names=["updated_at"])
    return temporary_rule


# --- 按规则发放 ---
async def grant_points_by_rule(
    session: AsyncSession,
    *,
    rule_id: int,
    user_id: int,
    operator_id: int | None,
    idempotency_key: str,
    business_id: str | None = None,
    reason: str | None = None,
) -> PointOperationResult:
    """
    按已生效积分规则给用户发放积分。

    这个函数是后续任务、值班、打扫卫生等业务域的内部入口。HTTP 层暂不开放“按规则
    手动发分”接口，避免规则审批绕一圈后又变成后台手动改分。
    """

    normalized_idempotency_key = normalize_idempotency_key(idempotency_key)
    normalized_reason = normalize_optional_reason(reason)
    repository = PointRuleRepository(session)
    rule = await repository.get_point_rule_by_id(rule_id)
    if rule is None:
        raise AppError("POINT_RULE_NOT_FOUND", "积分规则不存在", status_code=404)
    _ensure_rule_can_grant(rule)
    await ensure_user_exists(session, user_id=user_id)
    if operator_id is not None:
        await ensure_user_exists(session, user_id=operator_id)

    business_type = (
        "temporary_point_rule"
        if rule.rule_type == POINT_RULE_TYPE_TEMPORARY_TASK_TEMPLATE
        else "point_rule"
    )
    normalized_business_id = f"{rule.id}:{business_id}" if business_id else str(rule.id)
    existing = await get_existing_idempotent_result(
        session,
        idempotency_key=normalized_idempotency_key,
        user_id=user_id,
        business_type=business_type,
    )
    if existing is not None:
        return existing

    account = await get_or_create_point_account(session, user_id=user_id, for_update=True)
    ensure_account_active(account)
    account.balance += rule.amount
    entry = await append_ledger_entry(
        session,
        account=account,
        direction=POINT_DIRECTION_INCOME,
        amount=rule.amount,
        business_type=business_type,
        business_id=normalized_business_id,
        idempotency_key=normalized_idempotency_key,
        reason=normalized_reason or f"按积分规则发放：{rule.name}",
        operator_id=operator_id,
    )
    return PointOperationResult(account=account, ledger_entry=entry)


# --- 内部校验与记录工具 ---
async def _get_temporary_rule_or_404(
    repository: PointRuleRepository,
    *,
    rule_id: int,
) -> TemporaryPointRule:
    """读取临时规则申请，不存在时抛出业务错误。"""

    rule = await repository.get_temporary_rule_by_id(rule_id)
    if rule is None:
        raise AppError("TEMPORARY_POINT_RULE_NOT_FOUND", "临时积分规则不存在", status_code=404)
    return rule


async def _record_temporary_rule_event(
    repository: PointRuleRepository,
    *,
    rule_id: int,
    event_type: str,
    actor_id: int | None,
    reason: str | None = None,
    extra: dict | None = None,
) -> TemporaryPointRuleEvent:
    """写入临时积分规则生命周期事件。"""

    event = TemporaryPointRuleEvent(
        temporary_rule_id=rule_id,
        event_type=event_type,
        actor_id=actor_id,
        reason=reason,
        extra=extra,
    )
    return await repository.add_temporary_rule_event(event)


async def _ensure_department_exists(session: AsyncSession, *, department_id: int) -> None:
    """确认临时规则限定的部门存在且启用。"""

    department = await session.scalar(
        select(Department).where(Department.id == department_id, Department.status == "active"),
    )
    if department is None:
        raise AppError("DEPARTMENT_NOT_FOUND", "部门不存在或未启用", status_code=404)


def _ensure_effective_window(
    *,
    effective_from: datetime | None,
    effective_to: datetime | None,
) -> None:
    """校验积分规则有效期。"""

    if effective_from is not None and effective_to is not None:
        comparable_from, comparable_to = _align_datetime_pair(effective_from, effective_to)
        if comparable_to > comparable_from:
            return
        raise AppError("POINT_RULE_EFFECTIVE_WINDOW_INVALID", "积分规则结束时间必须晚于开始时间", status_code=422)


def _ensure_rule_can_grant(rule: PointRule) -> None:
    """确认积分规则当前可以用于发放。"""

    if rule.status != POINT_RULE_STATUS_ACTIVE:
        raise AppError("POINT_RULE_NOT_ACTIVE", "积分规则未启用或已撤回", status_code=409)
    if rule.effective_from is not None and rule.effective_from > _now_matching(rule.effective_from):
        raise AppError("POINT_RULE_NOT_EFFECTIVE", "积分规则尚未生效", status_code=409)
    if rule.effective_to is not None and rule.effective_to <= _now_matching(rule.effective_to):
        raise AppError("POINT_RULE_EXPIRED", "积分规则已过期", status_code=409)


def _append_operation_note(current: str | None, note: str) -> str:
    """给规则描述追加一条运维说明。"""

    if not current:
        return note
    return f"{current}\n{note}"


def _now_matching(value: datetime) -> datetime:
    """
    生成和目标 datetime 可比较的当前时间。

    SQLite 测试库会把 `timezone=True` 字段读回成 naive datetime；MySQL 生产库按配置保存
    时区语义。这里不改变业务时间，只在比较时对齐 tzinfo，避免测试库和生产库行为差异
    让规则有效期判断失真。
    """

    now = utc_now()
    if value.tzinfo is None:
        return now.replace(tzinfo=None)
    return now


def _align_datetime_pair(start: datetime, end: datetime) -> tuple[datetime, datetime]:
    """把一对 datetime 对齐到可比较状态。"""

    if start.tzinfo is None and end.tzinfo is not None:
        return start, end.replace(tzinfo=None)
    if start.tzinfo is not None and end.tzinfo is None:
        return start.replace(tzinfo=None), end
    return start, end
