# tests/test_infrastructure.py
"""
基础设施适配测试

本文件验证生产安全边界和健康检查语义，避免底层适配器在上线环境中误用。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.infrastructure.email import send_email_verification_code
from app.interfaces.http.v1.system import router as system_router_module
from app.main import create_app


@pytest.mark.asyncio
async def test_email_log_mode_is_forbidden_in_production(monkeypatch) -> None:
    """生产环境不允许把明文验证码写入运行日志。"""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "log")
    get_settings.cache_clear()

    try:
        with pytest.raises(AppError) as exc_info:
            await send_email_verification_code(
                email="ray@example.com",
                purpose="bind_email",
                code="123456",
                expires_minutes=5,
            )
    finally:
        get_settings.cache_clear()

    assert exc_info.value.code == "EMAIL_LOG_MODE_FORBIDDEN"


def test_readiness_returns_503_when_dependency_is_unhealthy(monkeypatch) -> None:
    """readiness 依赖异常时应返回 503，方便部署平台停止接流量。"""

    async def healthy_database() -> None:
        return None

    async def unhealthy_minio() -> None:
        raise RuntimeError("minio down")

    monkeypatch.setattr(system_router_module, "ping_database", healthy_database)
    monkeypatch.setattr(system_router_module, "ping_minio", unhealthy_minio)

    client = TestClient(create_app())
    response = client.get("/api/v1/health")

    assert response.status_code == 503
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "degraded"
    assert body["data"]["checks"][1]["name"] == "minio"
    assert body["data"]["checks"][1]["status"] == "unhealthy"
