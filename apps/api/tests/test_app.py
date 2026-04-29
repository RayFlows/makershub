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
