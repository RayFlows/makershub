# app/modules/points/types.py
"""
积分账本服务层结果对象

积分域会被借用、任务、项目、后台管理等多个业务入口调用。服务层返回明确的数据结构，
可以让接口层和其他业务域不用猜测某次操作是否命中幂等、是否关联冻结记录。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.points.models import PointAccount, PointHold, PointLedgerEntry


@dataclass(frozen=True)
class PointOperationResult:
    """积分操作结果。"""

    account: PointAccount
    ledger_entry: PointLedgerEntry
    hold: PointHold | None = None
    idempotent: bool = False


@dataclass(frozen=True)
class PointLedgerPage:
    """积分流水分页结果。"""

    items: list[PointLedgerEntry]
    page: int
    page_size: int
    total: int
