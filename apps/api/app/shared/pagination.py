# app/shared/pagination.py
"""
分页请求与响应模型

所有列表接口都应复用这里的分页结构，避免不同业务域各自定义 page/page_size 字段，
导致前端和 API 客户端适配成本上升。
"""

from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    """分页查询参数。

    page 从 1 开始，page_size 默认 20 且最大 100，避免一次查询拉取过多数据。
    sort/order 只描述请求意图，具体允许排序字段由各业务接口自行白名单校验。
    """

    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort: str | None = None
    order: Literal["asc", "desc"] = "desc"

    @property
    def offset(self) -> int:
        """转换成数据库查询常用的 offset。"""

        return (self.page - 1) * self.page_size


class PageResult(BaseModel, Generic[T]):
    """统一分页响应结构。"""

    items: list[T]
    page: int
    page_size: int
    total: int
