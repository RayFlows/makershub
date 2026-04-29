from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors.exceptions import AppError
from app.shared.request_context import get_request_id
from app.shared.responses import error_response


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        return error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=get_request_id(request),
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        return error_response(
            code="VALIDATION_ERROR",
            message="请求参数不合法",
            status_code=422,
            request_id=get_request_id(request),
            details={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        return error_response(
            code="HTTP_ERROR",
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=get_request_id(request),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        return error_response(
            code="INTERNAL_SERVER_ERROR",
            message="服务器内部错误",
            status_code=500,
            request_id=get_request_id(request),
            details={"error": exc.__class__.__name__},
        )
