# app/interfaces/http/v1/borrowing/schemas.py
"""
借用接口请求与响应模型

接口层 schema 只描述 HTTP 契约。申请能否审批、库存如何扣减、押金如何冻结，
由 borrowing.materials 服务层负责。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class BorrowApplicationItemRequest(BaseModel):
    """借用申请物资明细请求。"""

    material_id: int = Field(description="物资 ID")
    quantity: int = Field(gt=0, description="借用数量")


class BorrowApplicationCreateRequest(BaseModel):
    """创建借用申请请求。"""

    borrow_type: str = Field(default="material", description="借用类型，第一阶段仅支持 material")
    usage_type: str = Field(default="personal", description="用途：personal 或 project")
    project_id: int | None = Field(default=None, description="项目 ID，项目模块落地后开放")
    reason: str = Field(min_length=1, max_length=2000, description="借用理由")
    expected_return_at: datetime | None = Field(default=None, description="预计归还时间，第一阶段个人物资借用必填")
    items: list[BorrowApplicationItemRequest] = Field(min_length=1, description="借用物资明细")


class BorrowApplicationCancelRequest(BaseModel):
    """取消借用申请请求。"""

    cancel_reason: str | None = Field(default=None, max_length=1000, description="取消原因，可选")


class BorrowApplicationReviewRequest(BaseModel):
    """审核借用申请请求。"""

    decision: str = Field(description="审核动作：approve 或 reject")
    comment: str | None = Field(default=None, max_length=1000, description="审核意见，驳回时必填")


class BorrowApplicationReturnRequest(BaseModel):
    """确认归还请求。"""

    condition: str = Field(default="normal", description="归还情况：normal、damaged、lost 或 consumed")
    comment: str | None = Field(default=None, max_length=1000, description="归还备注，异常归还时必填")


class BorrowItemResponse(BaseModel):
    """借用明细响应。"""

    id: int
    resource_type: str
    material_id: int | None
    material_name: str
    category_name: str | None
    quantity: int
    unit_deposit_points: int
    subtotal_deposit_points: int


class BorrowApplicantSnapshotResponse(BaseModel):
    """申请人历史快照响应。"""

    name: str
    student_id: str
    phone: str
    email: str
    grade: str
    major: str


class BorrowApplicantSummaryResponse(BaseModel):
    """列表使用的申请人摘要响应。"""

    name: str
    grade: str
    major: str


class BorrowApplicantCurrentContactResponse(BaseModel):
    """申请人当前联系方式响应。"""

    phone: str | None
    email: str | None


class BorrowReviewResponse(BaseModel):
    """借用审核记录响应。"""

    id: int
    reviewer_id: int
    decision: str
    comment: str | None
    reviewed_at: datetime


class BorrowReturnResponse(BaseModel):
    """借用归还记录响应。"""

    id: int
    operator_id: int
    returned_at: datetime
    condition: str
    comment: str | None
    point_action: str | None


class BorrowApplicationResponse(BaseModel):
    """借用申请响应。"""

    id: int
    applicant_id: int
    applicant_snapshot: BorrowApplicantSnapshotResponse
    applicant_current_contact: BorrowApplicantCurrentContactResponse | None = None
    borrow_type: str
    usage_type: str
    project_id: int | None
    reason: str
    expected_return_at: datetime
    status: str
    deposit_points: int
    point_hold_id: int | None
    submitted_at: datetime
    cancelled_at: datetime | None
    cancel_reason: str | None
    items: list[BorrowItemResponse]
    reviews: list[BorrowReviewResponse]
    returns: list[BorrowReturnResponse]
    created_at: datetime
    updated_at: datetime


class BorrowApplicationListItemResponse(BaseModel):
    """借用申请列表项响应。"""

    id: int
    applicant_summary: BorrowApplicantSummaryResponse
    borrow_type: str
    usage_type: str
    project_id: int | None
    expected_return_at: datetime
    status: str
    deposit_points: int
    submitted_at: datetime
    material_summary: str
    created_at: datetime
    updated_at: datetime


class BorrowApplicationPageResponse(BaseModel):
    """借用申请分页响应。"""

    items: list[BorrowApplicationListItemResponse]
    page: int
    page_size: int
    total: int
