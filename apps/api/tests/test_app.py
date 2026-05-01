# tests/test_app.py
"""
应用入口与统一响应测试

本文件验证 FastAPI 应用基础能力：进程存活检查、统一错误响应和 request_id 透传。
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.main import create_app


def test_liveness_returns_unified_response() -> None:
    client = TestClient(create_app())

    response = client.get("/health")

    assert response.status_code == 200
    body = response.json()
    assert body["success"] is True
    assert body["data"]["status"] == "ok"
    assert body["request_id"].startswith("req_")
    assert response.headers["x-request-id"] == body["request_id"]


def test_validation_error_returns_unified_response() -> None:
    client = TestClient(create_app())

    response = client.get("/missing")

    assert response.status_code == 404
    body = response.json()
    assert body["success"] is False
    assert body["error"]["code"] == "HTTP_ERROR"
    assert body["request_id"].startswith("req_")
