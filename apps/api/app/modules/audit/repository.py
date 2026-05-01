# app/modules/audit/repository.py
"""
审计日志仓储

仓储只负责审计表读写，不判断某个业务动作是否应该被审计。是否需要审计由业务服务
和权限基础设施共同决定。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.audit.models import AuditLog


class AuditRepository:
    """审计日志数据库访问层。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, log: AuditLog) -> AuditLog:
        """新增一条审计日志。"""

        self.session.add(log)
        await self.session.flush()
        return log

    async def list_recent(self, *, limit: int = 50) -> list[AuditLog]:
        """按创建时间倒序读取最近审计日志。"""

        stmt = select(AuditLog).order_by(AuditLog.created_at.desc()).limit(limit)
        result = await self.session.scalars(stmt)
        return list(result)

