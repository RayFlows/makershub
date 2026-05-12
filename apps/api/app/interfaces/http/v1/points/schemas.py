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


class PointLedgerReverseRequest(BaseModel):
    """反向修正积分流水请求。"""

    reason: str = Field(min_length=1, max_length=500, description="反向修正原因")
    idempotency_key: str | None = Field(default=None, max_length=128, description="幂等键")


class PointRuleResponse(BaseModel):
    """积分规则响应。"""

    id: int
    code: str
    name: str
    rule_type: str
    status: str
    version: int
    amount: int
    description: str | None
    effective_from: datetime | None
    effective_to: datetime | None
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class PointRuleCreateRequest(BaseModel):
    """固定积分规则创建请求。"""

    code: str = Field(min_length=1, max_length=64, description="稳定规则 code")
    name: str = Field(min_length=1, max_length=120, description="规则名称")
    amount: int = Field(gt=0, description="单次发放积分")
    description: str | None = Field(default=None, max_length=500, description="规则说明")
    effective_from: datetime | None = Field(default=None, description="生效时间")
    effective_to: datetime | None = Field(default=None, description="失效时间")


class PointRuleRevokeRequest(BaseModel):
    """积分规则撤回请求。"""

    reason: str = Field(min_length=1, max_length=500, description="撤回原因")


class TemporaryPointRuleResponse(BaseModel):
    """临时积分规则响应。"""

    id: int
    name: str
    task_type: str
    target_scope: str
    department_id: int | None
    reason: str
    completion_requirements: str | None
    amount_per_completion: int
    max_participants: int
    total_points_limit: int
    effective_from: datetime
    effective_to: datetime
    approval_status: str
    applicant_id: int
    approved_by: int | None
    approved_at: datetime | None
    approval_reason: str | None
    rejected_by: int | None
    rejected_at: datetime | None
    rejection_reason: str | None
    generated_point_rule_id: int | None
    generated_point_rule: PointRuleResponse | None
    revoke_status: str
    revoked_by: int | None
    revoked_at: datetime | None
    revoke_reason: str | None
    revoke_impact_note: str | None
    created_at: datetime
    updated_at: datetime


class TemporaryPointRulePageResponse(BaseModel):
    """临时积分规则分页响应。"""

    items: list[TemporaryPointRuleResponse]
    page: int
    page_size: int
    total: int


class TemporaryPointRuleCreateRequest(BaseModel):
    """临时积分规则申请请求。"""

    name: str = Field(min_length=1, max_length=120, description="临时规则名称")
    task_type: str = Field(min_length=1, max_length=64, description="任务类型")
    target_scope: str = Field(min_length=1, max_length=64, description="适用对象")
    department_id: int | None = Field(default=None, description="限定部门 ID")
    reason: str = Field(min_length=1, max_length=500, description="申请原因")
    completion_requirements: str | None = Field(default=None, max_length=500, description="完成要求")
    amount_per_completion: int = Field(gt=0, description="每次完成发放积分")
    max_participants: int = Field(gt=0, description="最多参与人数")
    total_points_limit: int = Field(gt=0, description="总积分上限")
    effective_from: datetime = Field(description="生效时间")
    effective_to: datetime = Field(description="失效时间")


class TemporaryPointRuleApproveRequest(BaseModel):
    """临时积分规则审批通过请求。"""

    approval_reason: str = Field(min_length=1, max_length=500, description="审批理由")


class TemporaryPointRuleRejectRequest(BaseModel):
    """临时积分规则驳回请求。"""

    rejection_reason: str = Field(min_length=1, max_length=500, description="驳回理由")


class TemporaryPointRuleRevokeRequest(BaseModel):
    """临时积分规则撤回请求。"""

    revoke_reason: str = Field(min_length=1, max_length=500, description="撤回原因")
    revoke_impact_note: str = Field(min_length=1, max_length=500, description="影响范围和通知说明")
