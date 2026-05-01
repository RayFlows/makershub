# app/core/permissions/types.py
"""
权限基础类型

这里放权限系统共享的轻量类型，不依赖数据库和 FastAPI。
业务服务可以返回 PermissionDecision，接口层再决定转换成 403 还是继续执行。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

PermissionScope = Literal["global", "department", "project", "resource", "self"]


@dataclass(frozen=True)
class PermissionDecision:
    """
    权限判断结果。

    使用显式对象表达 allow/deny，方便后续把拒绝原因写入审计日志。
    """

    allowed: bool
    permission_code: str
    reason: str
    scope_type: PermissionScope | None = None
    scope_id: int | None = None
