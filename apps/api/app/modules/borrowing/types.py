# app/modules/borrowing/types.py
"""
借用域服务层结果对象

借用申请列表既服务“我的申请”，也服务审批端查看全部记录。服务层用分页结果承载查询
边界，接口层不直接拼 SQL 条件。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.borrowing.models import BorrowApplication


@dataclass(frozen=True)
class BorrowApplicationPage:
    """借用申请分页结果。"""

    items: list[BorrowApplication]
    page: int
    page_size: int
    total: int
