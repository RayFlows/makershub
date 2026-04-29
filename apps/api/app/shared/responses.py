from __future__ import annotations

from typing import Any

from starlette.responses import JSONResponse


def success_response(
    data: Any = None,
    *,
    message: str = "ok",
    request_id: str,
    status_code: int = 200,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": True,
            "data": data,
            "message": message,
            "request_id": request_id,
        },
    )


def error_response(
    *,
    code: str,
    message: str,
    status_code: int,
    request_id: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": details or {},
            },
            "request_id": request_id,
        },
    )
