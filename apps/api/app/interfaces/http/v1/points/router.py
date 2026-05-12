# app/interfaces/http/v1/points/router.py
"""
积分与账本 V1 路由

第一阶段开放当前用户积分账户和流水查看、后台积分账本查询，以及受控人工调整接口。
借用押金冻结、3D 打印接单冻结等业务操作先由 points 服务层提供能力，等对应业务域
落地时再开放外部 HTTP 契约。
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
    PointOperationResponse,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.points.accounts import get_or_create_point_account
from app.modules.points.adjustments import manually_adjust_points
from app.modules.points.ledger import list_point_ledger_entries
from app.modules.points.models import PointAccount, PointLedgerEntry
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


def build_account_snapshot(account: PointAccount) -> dict:
    """构造审计日志使用的账户快照。"""

    return build_point_account_response(account).model_dump(mode="json")


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
