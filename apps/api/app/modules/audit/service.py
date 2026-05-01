# app/modules/audit/service.py
"""
审计服务

业务服务在完成重要状态变更后调用这里写入审计日志。审计服务不提交事务，
这样审计记录可以和业务变更处在同一个数据库事务里：业务回滚时审计也回滚，
避免留下“操作成功但业务没落库”的假线索。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog
from app.modules.audit.repository import AuditRepository


@dataclass(frozen=True)
class AuditLogEntry:
    """审计日志写入参数。"""

    action: str
    target_type: str
    actor_id: int | None = None
    target_id: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    extra: dict[str, Any] | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    request_id: str | None = None
    reason: str | None = None
    result: str = "success"
    risk_level: str = "medium"


async def record_audit_log(session: AsyncSession, entry: AuditLogEntry) -> AuditLog:
    """
    写入审计日志。

    Args:
        session: 当前业务事务使用的数据库会话。
        entry: 审计日志参数。

    Returns:
        已加入当前事务的 AuditLog ORM 对象。
    """

    repository = AuditRepository(session)
    log = AuditLog(
        actor_id=entry.actor_id,
        action=entry.action,
        result=entry.result,
        risk_level=entry.risk_level,
        target_type=entry.target_type,
        target_id=entry.target_id,
        before_snapshot=entry.before_snapshot,
        after_snapshot=entry.after_snapshot,
        extra=entry.extra,
        ip_address=entry.ip_address,
        user_agent=entry.user_agent,
        request_id=entry.request_id,
        reason=entry.reason,
    )
    return await repository.add(log)

