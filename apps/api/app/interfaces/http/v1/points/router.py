# app/interfaces/http/v1/points/router.py
"""
积分与账本 V1 路由

第一阶段开放当前用户积分账户和流水查看、后台积分账本查询、受控人工调整、固定积分
规则和临时积分规则审批接口。冻结、解冻等业务操作先由 points 服务层提供能力，等对应
业务域落地时再开放外部 HTTP 契约。
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Header, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.errors import AppError
from app.core.security.middleware import get_client_ip
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.points.schemas import (
    ManualPointAdjustmentRequest,
    PointAccountResponse,
    PointLedgerEntryResponse,
    PointLedgerPageResponse,
    PointLedgerReverseRequest,
    PointOperationResponse,
    PointRuleCreateRequest,
    PointRuleResponse,
    PointRuleRevokeRequest,
    TemporaryPointRuleApproveRequest,
    TemporaryPointRuleCreateRequest,
    TemporaryPointRulePageResponse,
    TemporaryPointRuleRejectRequest,
    TemporaryPointRuleResponse,
    TemporaryPointRuleRevokeRequest,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.points.accounts import get_or_create_point_account
from app.modules.points.adjustments import manually_adjust_points
from app.modules.points.ledger import list_point_ledger_entries, reverse_ledger_entry
from app.modules.points.models import PointAccount, PointLedgerEntry, PointRule, TemporaryPointRule
from app.modules.points.rules import (
    approve_temporary_point_rule,
    create_point_rule,
    list_point_rules,
    list_temporary_point_rules,
    reject_temporary_point_rule,
    revoke_point_rule,
    revoke_temporary_point_rule,
    submit_temporary_point_rule,
)
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


# --- 响应转换 ---
def build_point_account_response(account: PointAccount) -> PointAccountResponse:
    """把积分账户 ORM 对象转换成接口响应。"""

    return PointAccountResponse(
        user_id=account.user_id,
        balance=account.balance,
        available_balance=account.available_balance,
        frozen_balance=account.frozen_balance,
        status=account.status,
        updated_at=account.updated_at,
    )


def build_point_ledger_entry_response(entry: PointLedgerEntry) -> PointLedgerEntryResponse:
    """把积分流水 ORM 对象转换成接口响应。"""

    return PointLedgerEntryResponse(
        id=entry.id,
        user_id=entry.user_id,
        direction=entry.direction,
        amount=entry.amount,
        balance_after=entry.balance_after,
        available_balance_after=entry.available_balance_after,
        frozen_balance_after=entry.frozen_balance_after,
        business_type=entry.business_type,
        business_id=entry.business_id,
        idempotency_key=entry.idempotency_key,
        related_hold_id=entry.related_hold_id,
        reason=entry.reason,
        operator_id=entry.operator_id,
        created_at=entry.created_at,
    )


def build_point_rule_response(rule: PointRule) -> PointRuleResponse:
    """把积分规则 ORM 对象转换成接口响应。"""

    return PointRuleResponse(
        id=rule.id,
        code=rule.code,
        name=rule.name,
        rule_type=rule.rule_type,
        status=rule.status,
        version=rule.version,
        amount=rule.amount,
        description=rule.description,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        created_by=rule.created_by,
        updated_by=rule.updated_by,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def build_temporary_point_rule_response(rule: TemporaryPointRule) -> TemporaryPointRuleResponse:
    """把临时积分规则 ORM 对象转换成接口响应。"""

    generated_rule = (
        build_point_rule_response(rule.generated_point_rule)
        if rule.generated_point_rule is not None
        else None
    )
    return TemporaryPointRuleResponse(
        id=rule.id,
        name=rule.name,
        task_type=rule.task_type,
        target_scope=rule.target_scope,
        department_id=rule.department_id,
        reason=rule.reason,
        completion_requirements=rule.completion_requirements,
        amount_per_completion=rule.amount_per_completion,
        max_participants=rule.max_participants,
        total_points_limit=rule.total_points_limit,
        effective_from=rule.effective_from,
        effective_to=rule.effective_to,
        approval_status=rule.approval_status,
        applicant_id=rule.applicant_id,
        approved_by=rule.approved_by,
        approved_at=rule.approved_at,
        approval_reason=rule.approval_reason,
        rejected_by=rule.rejected_by,
        rejected_at=rule.rejected_at,
        rejection_reason=rule.rejection_reason,
        generated_point_rule_id=rule.generated_point_rule_id,
        generated_point_rule=generated_rule,
        revoke_status=rule.revoke_status,
        revoked_by=rule.revoked_by,
        revoked_at=rule.revoked_at,
        revoke_reason=rule.revoke_reason,
        revoke_impact_note=rule.revoke_impact_note,
        created_at=rule.created_at,
        updated_at=rule.updated_at,
    )


def build_account_snapshot(account: PointAccount) -> dict:
    """构造审计日志使用的账户快照。"""

    return build_point_account_response(account).model_dump(mode="json")


def build_point_rule_snapshot(rule: PointRule) -> dict:
    """构造审计日志使用的积分规则快照。"""

    return build_point_rule_response(rule).model_dump(mode="json")


def build_temporary_rule_snapshot(rule: TemporaryPointRule) -> dict:
    """构造审计日志使用的临时规则快照。"""

    return build_temporary_point_rule_response(rule).model_dump(mode="json")


# --- 当前用户积分 ---
@router.get("/me/points/account")
async def get_my_point_account(
    request: Request,
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查看当前用户自己的积分账户。"""

    account = await get_or_create_point_account(session, user_id=current_user.user.id)
    await session.commit()
    data = build_point_account_response(account)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/me/points/ledger")
async def get_my_point_ledger(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    current_user: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查看当前用户自己的积分流水。"""

    page_data = await list_point_ledger_entries(
        session,
        user_id=current_user.user.id,
        page=page,
        page_size=page_size,
    )
    data = PointLedgerPageResponse(
        items=[build_point_ledger_entry_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


# --- 后台积分账本 ---
@router.get("/points/accounts/{user_id}")
async def get_user_point_account(
    user_id: int,
    request: Request,
    _: CurrentUser = Depends(require_permission("points.ledger.view")),
    session: AsyncSession = Depends(get_session),
):
    """后台查看指定用户积分账户。"""

    account = await get_or_create_point_account(session, user_id=user_id)
    await session.commit()
    data = build_point_account_response(account)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/points/ledger")
async def get_point_ledger(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    user_id: int | None = Query(default=None),
    _: CurrentUser = Depends(require_permission("points.ledger.view")),
    session: AsyncSession = Depends(get_session),
):
    """后台查询积分流水。"""

    page_data = await list_point_ledger_entries(
        session,
        user_id=user_id,
        page=page,
        page_size=page_size,
    )
    data = PointLedgerPageResponse(
        items=[build_point_ledger_entry_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/ledger/{ledger_entry_id}/reverse")
async def reverse_point_ledger(
    ledger_entry_id: int,
    payload: PointLedgerReverseRequest,
    request: Request,
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: CurrentUser = Depends(require_permission("points.manual.adjust")),
    session: AsyncSession = Depends(get_session),
):
    """
    后台受控反向修正积分流水。

    该接口属于 998/999 系统兜底和异常修复能力，不是日常积分规则审批入口。
    """

    idempotency_key = payload.idempotency_key or idempotency_key_header
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "反向修正积分流水必须提供幂等键", status_code=422)

    result = await reverse_ledger_entry(
        session,
        ledger_entry_id=ledger_entry_id,
        reason=payload.reason,
        operator_id=current_user.user.id,
        idempotency_key=idempotency_key,
    )
    if not result.idempotent:
        await record_audit_log(
            session,
            AuditLogEntry(
                actor_id=current_user.user.id,
                action="points.ledger.reverse",
                target_type="point_ledger_entry",
                target_id=str(ledger_entry_id),
                after_snapshot=build_point_ledger_entry_response(result.ledger_entry).model_dump(mode="json"),
                extra={
                    "target_user_id": result.account.user_id,
                    "reversal_ledger_entry_id": result.ledger_entry.id,
                    "idempotency_key": idempotency_key,
                },
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                request_id=get_request_id(request),
                reason=payload.reason,
                risk_level="critical",
            ),
        )
    await session.commit()
    data = PointOperationResponse(
        account=build_point_account_response(result.account),
        ledger_entry=build_point_ledger_entry_response(result.ledger_entry),
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


# --- 积分规则 ---
@router.get("/points/rules")
async def get_point_rules(
    request: Request,
    include_revoked: bool = Query(default=False),
    rule_type: str | None = Query(default=None),
    _: CurrentUser = Depends(require_permission("points.rule.view")),
    session: AsyncSession = Depends(get_session),
):
    """后台查看固定规则和一次性任务模板。"""

    rules = await list_point_rules(
        session,
        include_revoked=include_revoked,
        rule_type=rule_type,
    )
    data = [build_point_rule_response(item).model_dump(mode="json") for item in rules]
    return success_response(data, request_id=get_request_id(request))


@router.post("/points/rules")
async def create_fixed_point_rule(
    payload: PointRuleCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("points.rule.manage")),
    session: AsyncSession = Depends(get_session),
):
    """后台创建固定积分规则。"""

    rule = await create_point_rule(
        session,
        code=payload.code,
        name=payload.name,
        amount=payload.amount,
        description=payload.description,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
        operator_id=current_user.user.id,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="points.rule.create",
            target_type="point_rule",
            target_id=str(rule.id),
            after_snapshot=build_point_rule_snapshot(rule),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.description,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_point_rule_response(rule)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/rules/{rule_id}/revoke")
async def revoke_fixed_point_rule(
    rule_id: int,
    payload: PointRuleRevokeRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("points.rule.manage")),
    session: AsyncSession = Depends(get_session),
):
    """后台撤回固定积分规则或一次性任务模板。"""

    rules_before = await list_point_rules(session, include_revoked=True)
    before_rule = next((item for item in rules_before if item.id == rule_id), None)
    before_snapshot = build_point_rule_snapshot(before_rule) if before_rule is not None else None
    rule = await revoke_point_rule(
        session,
        rule_id=rule_id,
        reason=payload.reason,
        operator_id=current_user.user.id,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="points.rule.revoke",
            target_type="point_rule",
            target_id=str(rule.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_point_rule_snapshot(rule),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_point_rule_response(rule)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/points/rules/temporary")
async def get_temporary_point_rules(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    approval_status: str | None = Query(default=None),
    _: CurrentUser = Depends(require_permission("points.rule.view")),
    session: AsyncSession = Depends(get_session),
):
    """后台分页查看临时积分规则申请。"""

    page_data = await list_temporary_point_rules(
        session,
        page=page,
        page_size=page_size,
        approval_status=approval_status,
    )
    data = TemporaryPointRulePageResponse(
        items=[build_temporary_point_rule_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/rules/temporary")
async def create_temporary_point_rule(
    payload: TemporaryPointRuleCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("points.temporary_rule.apply")),
    session: AsyncSession = Depends(get_session),
):
    """后台提交临时积分规则申请。"""

    rule = await submit_temporary_point_rule(
        session,
        applicant_id=current_user.user.id,
        name=payload.name,
        task_type=payload.task_type,
        target_scope=payload.target_scope,
        department_id=payload.department_id,
        reason=payload.reason,
        completion_requirements=payload.completion_requirements,
        amount_per_completion=payload.amount_per_completion,
        max_participants=payload.max_participants,
        total_points_limit=payload.total_points_limit,
        effective_from=payload.effective_from,
        effective_to=payload.effective_to,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="points.temporary_rule.submit",
            target_type="temporary_point_rule",
            target_id=str(rule.id),
            after_snapshot=build_temporary_rule_snapshot(rule),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_temporary_point_rule_response(rule)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/rules/temporary/{rule_id}/approve")
async def approve_temporary_rule(
    rule_id: int,
    payload: TemporaryPointRuleApproveRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("points.temporary_rule.review")),
    session: AsyncSession = Depends(get_session),
):
    """后台审批通过临时积分规则。"""

    rule = await approve_temporary_point_rule(
        session,
        rule_id=rule_id,
        approver_id=current_user.user.id,
        approval_reason=payload.approval_reason,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="points.temporary_rule.approve",
            target_type="temporary_point_rule",
            target_id=str(rule.id),
            after_snapshot=build_temporary_rule_snapshot(rule),
            extra={"generated_point_rule_id": rule.generated_point_rule_id},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.approval_reason,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_temporary_point_rule_response(rule)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/rules/temporary/{rule_id}/reject")
async def reject_temporary_rule(
    rule_id: int,
    payload: TemporaryPointRuleRejectRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("points.temporary_rule.review")),
    session: AsyncSession = Depends(get_session),
):
    """后台驳回临时积分规则。"""

    rule = await reject_temporary_point_rule(
        session,
        rule_id=rule_id,
        reviewer_id=current_user.user.id,
        rejection_reason=payload.rejection_reason,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="points.temporary_rule.reject",
            target_type="temporary_point_rule",
            target_id=str(rule.id),
            after_snapshot=build_temporary_rule_snapshot(rule),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.rejection_reason,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_temporary_point_rule_response(rule)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/rules/temporary/{rule_id}/revoke")
async def revoke_temporary_rule(
    rule_id: int,
    payload: TemporaryPointRuleRevokeRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("points.temporary_rule.review")),
    session: AsyncSession = Depends(get_session),
):
    """后台撤回已发布的临时积分规则。"""

    rule = await revoke_temporary_point_rule(
        session,
        rule_id=rule_id,
        operator_id=current_user.user.id,
        revoke_reason=payload.revoke_reason,
        revoke_impact_note=payload.revoke_impact_note,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="points.temporary_rule.revoke",
            target_type="temporary_point_rule",
            target_id=str(rule.id),
            after_snapshot=build_temporary_rule_snapshot(rule),
            extra={"revoke_impact_note": payload.revoke_impact_note},
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.revoke_reason,
            risk_level="critical",
        ),
    )
    await session.commit()
    data = build_temporary_point_rule_response(rule)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/points/manual-adjustments")
async def create_manual_point_adjustment(
    payload: ManualPointAdjustmentRequest,
    request: Request,
    idempotency_key_header: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    current_user: CurrentUser = Depends(require_permission("points.manual.adjust")),
    session: AsyncSession = Depends(get_session),
):
    """
    后台受控人工调整积分。

    该接口服务 998/999 的系统级兜底和异常修复，不能作为日常积分规则审批入口。
    """

    idempotency_key = payload.idempotency_key or idempotency_key_header
    if not idempotency_key:
        raise AppError("IDEMPOTENCY_KEY_REQUIRED", "人工积分调整必须提供幂等键", status_code=422)

    before_account = await get_or_create_point_account(session, user_id=payload.user_id, for_update=True)
    before_snapshot = build_account_snapshot(before_account)
    result = await manually_adjust_points(
        session,
        user_id=payload.user_id,
        amount=payload.amount,
        reason=payload.reason,
        operator_id=current_user.user.id,
        idempotency_key=idempotency_key,
        business_id=payload.business_id,
    )
    after_snapshot = build_account_snapshot(result.account)
    if not result.idempotent:
        await record_audit_log(
            session,
            AuditLogEntry(
                actor_id=current_user.user.id,
                action="points.manual_adjustment.create",
                target_type="point_account",
                target_id=str(result.account.id),
                before_snapshot=before_snapshot,
                after_snapshot=after_snapshot,
                extra={
                    "target_user_id": payload.user_id,
                    "ledger_entry_id": result.ledger_entry.id,
                    "amount": payload.amount,
                    "idempotency_key": idempotency_key,
                },
                ip_address=get_client_ip(request),
                user_agent=request.headers.get("user-agent"),
                request_id=get_request_id(request),
                reason=payload.reason,
                risk_level="high",
            ),
        )
    await session.commit()
    data = PointOperationResponse(
        account=build_point_account_response(result.account),
        ledger_entry=build_point_ledger_entry_response(result.ledger_entry),
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))
