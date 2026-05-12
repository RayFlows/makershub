# app/interfaces/http/v1/points/schemas.py
"""
积分与账本接口请求与响应模型

接口层 schema 只描述 HTTP 契约。余额是否允许变化、流水如何幂等、冻结能否扣除，
由 points 域内具体能力模块负责。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class PointAccountResponse(BaseModel):
    """积分账户响应。"""

    user_id: int
    balance: int
    available_balance: int
    frozen_balance: int
    status: str
    updated_at: datetime


class PointLedgerEntryResponse(BaseModel):
    """积分流水响应。"""

    id: int
    user_id: int
    direction: str
    amount: int
    balance_after: int
    available_balance_after: int
    frozen_balance_after: int
    business_type: str
    business_id: str | None
    idempotency_key: str | None
    related_hold_id: int | None
    reason: str | None
    operator_id: int | None
    created_at: datetime


class PointLedgerPageResponse(BaseModel):
    """积分流水分页响应。"""

    items: list[PointLedgerEntryResponse]
    page: int
    page_size: int
    total: int


class ManualPointAdjustmentRequest(BaseModel):
    """后台人工调整积分请求。"""

    user_id: int = Field(description="目标用户 ID")
    amount: int = Field(description="调整数量，正数为增加，负数为扣减")
    reason: str = Field(min_length=1, max_length=500, description="调整原因")
    idempotency_key: str | None = Field(default=None, max_length=128, description="幂等键")
    business_id: str | None = Field(default=None, max_length=128, description="外部业务单据 ID")


class PointOperationResponse(BaseModel):
    """积分操作响应。"""

    account: PointAccountResponse
    ledger_entry: PointLedgerEntryResponse
