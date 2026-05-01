# app/interfaces/http/v1/system/router.py
"""
系统健康检查路由

/health 用于本地开发、Docker Compose 和后续部署平台判断服务是否可用。
这里区分 liveness 和 readiness：根路径 /health 在 main.py 中只证明进程存活；
/api/v1/health 会检查数据库和对象存储等依赖是否可用。
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import APIRouter, Request

from app.core.config.settings import get_settings
from app.core.database import ping_database
from app.infrastructure.minio import ping_minio
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


async def check_dependency(name: str, check: Callable[[], Awaitable[None]]) -> dict[str, str]:
    """
    执行单个依赖健康检查。

    Args:
        name: 依赖名称，例如 database/minio。
        check: 无参数异步检查函数，成功返回 None，失败抛出异常。

    Returns:
        统一的依赖检查结果字典。
    """

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
    """
    服务依赖就绪检查。

    Returns:
        包含数据库、MinIO 等依赖状态的统一响应。
        当某个依赖异常时，整体 status 为 degraded，并返回 503 供部署平台识别。
    """

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
        status_code=200 if status == "ok" else 503,
    )
