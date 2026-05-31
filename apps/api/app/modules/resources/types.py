# app/modules/resources/types.py
"""
资源域服务层结果对象

资源列表会被成员端、后台管理端和借用申请页复用。服务层返回明确分页对象，
接口层只负责协议转换，不猜测查询条件和分页含义。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.resources.models import Material, ResourceCategory


@dataclass(frozen=True)
class MaterialPage:
    """物资分页结果。"""

    items: list[Material]
    page: int
    page_size: int
    total: int


@dataclass(frozen=True)
class ResourceCategoryPage:
    """资源分类分页结果。"""

    items: list[ResourceCategory]
    page: int
    page_size: int
    total: int
