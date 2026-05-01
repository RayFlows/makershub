# app/interfaces/http/v1/audit/router.py
"""
审计 V1 路由

审计日志是后台和运维排查的重要入口，只允许拥有 `system.audit.view`
权限的用户读取。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.interfaces.http.dependencies import CurrentUser, require_permission
from app.interfaces.http.v1.audit.schemas import AuditLogItem
from app.modules.audit.repository import AuditRepository
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter(prefix="/audit")


@router.get("/logs")
async def list_audit_logs(
    request: Request,
    limit: int = Query(default=50, ge=1, le=200),
    _: CurrentUser = Depends(require_permission("system.audit.view")),
    session: AsyncSession = Depends(get_session),
):
    """读取最近审计日志。"""

    repository = AuditRepository(session)
    logs = await repository.list_recent(limit=limit)
    data = [
        AuditLogItem(
            id=item.id,
            actor_id=item.actor_id,
            action=item.action,
            result=item.result,
            risk_level=item.risk_level,
            target_type=item.target_type,
            target_id=item.target_id,
            before_snapshot=item.before_snapshot,
            after_snapshot=item.after_snapshot,
            extra=item.extra,
            request_id=item.request_id,
            reason=item.reason,
            created_at=item.created_at,
        ).model_dump(mode="json")
        for item in logs
    ]
    return success_response({"logs": data}, request_id=get_request_id(request))

