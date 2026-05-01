# app/interfaces/http/v1/audit/schemas.py
"""
审计接口响应模型

审计响应默认不展开敏感快照字段的展示策略，后续后台页面需要根据权限和场景
决定是否展示 before/after 的完整内容。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel


class AuditLogItem(BaseModel):
    """审计日志响应项。"""

    id: int
    actor_id: int | None
    action: str
    result: str
    risk_level: str
    target_type: str
    target_id: str | None
    before_snapshot: dict[str, Any] | None
    after_snapshot: dict[str, Any] | None
    extra: dict[str, Any] | None
    request_id: str | None
    reason: str | None
    created_at: datetime

