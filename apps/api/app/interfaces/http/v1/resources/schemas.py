# app/interfaces/http/v1/resources/schemas.py
"""
资源接口请求与响应模型

接口层 schema 只描述 HTTP 契约。物资是否可借、库存能否调整、分类是否启用，
由 resources.materials 服务层负责。
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ResourceCategoryResponse(BaseModel):
    """资源分类响应。"""

    id: int
    name: str
    resource_type: str
    status: str
    sort_order: int
    created_at: datetime
    updated_at: datetime


class ResourceCategoryPageResponse(BaseModel):
    """资源分类分页响应。"""

    items: list[ResourceCategoryResponse]
    page: int
    page_size: int
    total: int


class ResourceCategoryCreateRequest(BaseModel):
    """创建资源分类请求。"""

    name: str = Field(min_length=1, max_length=120, description="分类名称")
    status: str = Field(default="active", description="分类状态：active 或 disabled")
    sort_order: int = Field(default=0, description="排序值，越小越靠前")


class MaterialResponse(BaseModel):
    """物资响应。"""

    id: int
    category_id: int | None
    category_name: str | None
    name: str
    description: str | None
    location: str | None
    cabinet_no: str | None
    shelf_no: str | None
    status: str
    total_quantity: int
    available_quantity: int
    deposit_points: int
    created_by: int | None
    updated_by: int | None
    created_at: datetime
    updated_at: datetime


class MaterialPageResponse(BaseModel):
    """物资分页响应。"""

    items: list[MaterialResponse]
    page: int
    page_size: int
    total: int


class MaterialCreateRequest(BaseModel):
    """创建物资请求。"""

    name: str = Field(min_length=1, max_length=120, description="物资名称")
    category_id: int | None = Field(default=None, description="物资分类 ID")
    description: str | None = Field(default=None, max_length=2000, description="物资说明")
    location: str | None = Field(default=None, max_length=120, description="存放位置")
    cabinet_no: str | None = Field(default=None, max_length=80, description="柜号")
    shelf_no: str | None = Field(default=None, max_length=80, description="层号")
    status: str = Field(default="available", description="物资状态")
    total_quantity: int = Field(ge=0, description="总数量")
    available_quantity: int | None = Field(default=None, ge=0, description="可借数量，默认等于总数量")
    deposit_points: int = Field(default=0, ge=0, description="单件押金积分")


class MaterialUpdateRequest(BaseModel):
    """更新物资基础资料请求。"""

    name: str | None = Field(default=None, min_length=1, max_length=120, description="物资名称")
    category_id: int | None = Field(default=None, description="物资分类 ID")
    description: str | None = Field(default=None, max_length=2000, description="物资说明")
    location: str | None = Field(default=None, max_length=120, description="存放位置")
    cabinet_no: str | None = Field(default=None, max_length=80, description="柜号")
    shelf_no: str | None = Field(default=None, max_length=80, description="层号")
    status: str | None = Field(default=None, description="物资状态")
    deposit_points: int | None = Field(default=None, ge=0, description="单件押金积分")


class MaterialStockUpdateRequest(BaseModel):
    """调整物资库存请求。"""

    total_quantity: int = Field(ge=0, description="调整后的总数量")
    available_quantity: int = Field(ge=0, description="调整后的可借数量")
    reason: str = Field(min_length=1, max_length=1000, description="库存调整原因")
