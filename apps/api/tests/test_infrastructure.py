# tests/test_infrastructure.py
"""
基础设施适配测试

本文件验证生产安全边界和健康检查语义，避免底层适配器在上线环境中误用。
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.infrastructure.email import send_email_verification_code
from app.infrastructure.email.templates import build_email_verification_message
from app.interfaces.http.v1.system import router as system_router_module
from app.main import create_app


def set_secure_production_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """设置能通过生产安全校验的测试环境变量。"""

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("EMAIL_DELIVERY_MODE", "smtp")
    monkeypatch.setenv("CORS_ORIGINS", "https://mc.scumaker.com")
    monkeypatch.setenv("JWT_SECRET_KEY", "test-production-jwt-secret-value-0001")
    monkeypatch.setenv("MINIO_ACCESS_KEY", "test-production-minio-access")
    monkeypatch.setenv("MINIO_SECRET_KEY", "test-production-minio-secret-0001")


def test_security_headers_are_applied() -> None:
    """普通响应应带基础安全响应头。"""

    client = TestClient(create_app())
    response = client.get("/health")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    expected_permissions_policy = "camera=(), microphone=(), geolocation=(), payment=()"
    assert response.headers["permissions-policy"] == expected_permissions_policy


def test_hsts_header_is_enabled_in_production(monkeypatch) -> None:
    """生产环境默认发送 HSTS 响应头。"""

    set_secure_production_env(monkeypatch)
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        response = client.get("/health")
    finally:
        get_settings.cache_clear()

    assert response.headers["strict-transport-security"].startswith("max-age=63072000")


def test_production_rejects_wildcard_cors(monkeypatch) -> None:
    """生产环境不允许使用通配 CORS。"""

    set_secure_production_env(monkeypatch)
    monkeypatch.setenv("CORS_ORIGINS", "*")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError):
            create_app()
    finally:
        get_settings.cache_clear()


def test_request_size_limit_rejects_oversized_body(monkeypatch) -> None:
    """超过全局请求体上限时应返回 413。"""

    monkeypatch.setenv("MAX_REQUEST_BODY_BYTES", "8")
    monkeypatch.setenv("RATE_LIMIT_ENABLED", "false")
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        response = client.post(
            "/api/v1/auth/wechat/login",
            content=b'{"code":"too-large"}',
            headers={"content-type": "application/json"},
        )
    finally:
        get_settings.cache_clear()

    assert response.status_code == 413
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "REQUEST_BODY_TOO_LARGE"
    assert response.headers["x-request-id"] == body["request_id"]


def test_rate_limit_rejects_excessive_requests(monkeypatch) -> None:
    """应用层限流超过窗口额度时应返回 429。"""

    monkeypatch.setenv("RATE_LIMIT_MAX_REQUESTS", "1")
    monkeypatch.setenv("RATE_LIMIT_EXEMPT_PATHS", "/health")
    get_settings.cache_clear()

    try:
        client = TestClient(create_app())
        first = client.get("/missing")
        second = client.get("/missing")
    finally:
        get_settings.cache_clear()

    assert first.status_code == 404
    assert second.status_code == 429
    body = second.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert second.headers["retry-after"]


def test_production_rejects_default_jwt_secret(monkeypatch) -> None:
    """生产环境不能使用本地默认 JWT 密钥。"""

    set_secure_production_env(monkeypatch)
    monkeypatch.setenv("JWT_SECRET_KEY", "ChangeMeInProduction")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError, match="JWT_SECRET_KEY"):
            create_app()
    finally:
        get_settings.cache_clear()


def test_production_rejects_default_minio_secret(monkeypatch) -> None:
    """生产环境不能使用本地默认 MinIO 凭据。"""

    set_secure_production_env(monkeypatch)
    monkeypatch.setenv("MINIO_ACCESS_KEY", "makershub")
    monkeypatch.setenv("MINIO_SECRET_KEY", "makershub_minio")
    get_settings.cache_clear()

    try:
        with pytest.raises(ValidationError, match="MINIO_ACCESS_KEY"):
            create_app()
    finally:
        get_settings.cache_clear()


@pytest.mark.asyncio
async def test_email_log_mode_is_forbidden_in_production(monkeypatch) -> None:
    """生产环境不允许把明文验证码写入运行日志。"""

    set_secure_production_env(monkeypatch)
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


def test_email_verification_message_has_html_text_and_brand_header() -> None:
    """验证码邮件应同时提供 HTML、纯文本和稳定品牌头。"""

    message = build_email_verification_message(
        email="member@example.com",
        purpose="bind_email",
        code="123456",
        expires_minutes=5,
        from_email="auth@scumaker.com",
        from_name="MakersHub",
        home_url="https://scumaker.com",
        brand_image_url="https://static.scumaker.com/public/brand/SCUMAKER_logowithtext_email.png",
    )
    parts = list(message.walk())
    text_part = next(part for part in parts if part.get_content_type() == "text/plain")
    html_part = next(part for part in parts if part.get_content_type() == "text/html")

    assert message["Subject"] == "MakersHub 邮箱验证码"
    assert "123456" in text_part.get_content()
    assert "绑定邮箱" in text_part.get_content()
    assert "https://scumaker.com" in text_part.get_content()
    assert "https://scumaker.com" in html_part.get_content()
    assert "SCUMAKER_logowithtext_email.png" in html_part.get_content()
    assert "<img" in html_part.get_content()
    assert 'content="light only"' in html_part.get_content()
    assert 'bgcolor="#fffffe"' in html_part.get_content()
    assert "background-color:#fffffe" in html_part.get_content()
    assert "linear-gradient(#fffffe,#fffffe)" in html_part.get_content()
    assert "#f3f5f7" not in html_part.get_content()
    assert "border-left" not in html_part.get_content()
    assert "cid:" not in html_part.get_content()
    assert "123456" in html_part.get_content()


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
