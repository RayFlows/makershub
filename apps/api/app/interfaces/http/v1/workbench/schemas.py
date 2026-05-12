# app/interfaces/http/v1/workbench/schemas.py
"""
工作台接口请求与响应模型

接口层 schema 只描述 HTTP 契约。任务能否领取、能否提交、审核通过后如何发分，
由 workbench.tasks 服务层负责。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class WorkbenchTaskResponse(BaseModel):
    """工作台任务响应。"""

    id: int
    title: str
    task_type: str
    assignment_type: str
    visibility: str
    department_id: int | None
    content: str
    deadline: datetime | None
    status: str
    publisher_id: int
    assignee_id: int | None
    claimed_at: datetime | None
    point_rule_id: int
    point_rule_amount: int
    submission_content: str | None
    submitted_at: datetime | None
    reviewed_by: int | None
    reviewed_at: datetime | None
    review_comment: str | None
    completed_at: datetime | None
    point_ledger_entry_id: int | None
    created_at: datetime
    updated_at: datetime


class WorkbenchTaskPageResponse(BaseModel):
    """工作台任务分页响应。"""

    items: list[WorkbenchTaskResponse]
    page: int
    page_size: int
    total: int


class WorkbenchTaskCreateRequest(BaseModel):
    """工作台任务发布请求。"""

    title: str = Field(min_length=1, max_length=120, description="任务标题")
    task_type: str = Field(min_length=1, max_length=64, description="任务类型")
    assignment_type: str = Field(description="任务分配方式：assigned 或 bounty")
    visibility: str = Field(description="可见范围：department、association 或 public")
    department_id: int | None = Field(default=None, description="部门任务所属部门")
    content: str = Field(min_length=1, max_length=2000, description="任务内容")
    deadline: datetime | None = Field(default=None, description="任务截止时间")
    point_rule_id: int = Field(description="任务引用的积分规则 ID")
    assignee_id: int | None = Field(default=None, description="指定任务执行人 ID")


class WorkbenchTaskSubmitRequest(BaseModel):
    """任务完成提交请求。"""

    submission_content: str = Field(min_length=1, max_length=2000, description="完成材料或说明")


class WorkbenchTaskReviewRequest(BaseModel):
    """任务审核请求。"""

    action: str = Field(description="审核动作：approve 或 reject")
    review_comment: str | None = Field(default=None, max_length=1000, description="审核意见")
