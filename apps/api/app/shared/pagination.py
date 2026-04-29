from __future__ import annotations

from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams(BaseModel):
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)
    sort: str | None = None
    order: Literal["asc", "desc"] = "desc"

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size


class PageResult(BaseModel, Generic[T]):
    items: list[T]
    page: int
    page_size: int
    total: int
