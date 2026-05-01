# tests/test_audit.py
"""
审计基础设施测试

审计日志用于重要操作追踪，必须能和业务事务一起写入，并按时间倒序读取。
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.base import Base
from app.modules.audit.repository import AuditRepository
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.identity.models import User


@pytest.mark.asyncio
async def test_record_audit_log_persists_snapshots() -> None:
    """审计服务应该保存目标、结果和前后快照。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _ = User
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        log = await record_audit_log(
            session,
            AuditLogEntry(
                action="organization.member.update",
                target_type="member_profile",
                target_id="42",
                before_snapshot={"real_name": "旧名字"},
                after_snapshot={"real_name": "新名字"},
                request_id="req_test",
                reason="测试审计",
            ),
        )
        await session.commit()
        log_id = log.id

    async with session_factory() as session:
        logs = await AuditRepository(session).list_recent(limit=10)

    assert logs[0].id == log_id
    assert logs[0].action == "organization.member.update"
    assert logs[0].before_snapshot == {"real_name": "旧名字"}
    assert logs[0].after_snapshot == {"real_name": "新名字"}
    assert logs[0].request_id == "req_test"

    await engine.dispose()
