from __future__ import annotations

from fastapi import APIRouter, Request

from app.core.config.settings import get_settings
from app.core.database import ping_database
from app.infrastructure.minio import ping_minio
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


async def check_dependency(name: str, check) -> dict[str, str]:
    try:
        await check()
    except Exception as exc:
        return {
            "name": name,
            "status": "unhealthy",
            "error": exc.__class__.__name__,
        }

    return {"name": name, "status": "ok"}


@router.get("/health")
async def readiness(request: Request):
    settings = get_settings()
    checks = [
        await check_dependency("database", ping_database),
        await check_dependency("minio", ping_minio),
    ]
    status = "ok" if all(check["status"] == "ok" for check in checks) else "degraded"

    return success_response(
        {
            "status": status,
            "service": settings.app_name,
            "env": settings.app_env,
            "checks": checks,
        },
        request_id=get_request_id(request),
    )
