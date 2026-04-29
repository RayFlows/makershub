# app/core/errors/handlers.py
"""
统一异常处理模块

所有错误最终都收敛到 shared.responses.error_response，保证前端、小程序和后台
拿到一致的响应结构，也保证 request_id 可以贯穿日志和客户端报错。
"""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.errors.exceptions import AppError
from app.shared.request_context import get_request_id
from app.shared.responses import error_response


def register_exception_handlers(app: FastAPI) -> None:
    """注册全局异常处理器。

    注册顺序保持从业务异常到框架异常，再到兜底异常，避免已知错误被 500 吞掉。
    """

    @app.exception_handler(AppError)
    async def handle_app_error(request: Request, exc: AppError):
        """业务层显式抛出的错误，直接使用业务错误码和状态码。"""

        return error_response(
            code=exc.code,
            message=exc.message,
            status_code=exc.status_code,
            request_id=get_request_id(request),
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        """FastAPI/Pydantic 参数校验错误，统一转换成前端可识别的格式。"""

        return error_response(
            code="VALIDATION_ERROR",
            message="请求参数不合法",
            status_code=422,
            request_id=get_request_id(request),
            details={"errors": exc.errors()},
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_error(request: Request, exc: StarletteHTTPException):
        """路由不存在、方法不允许等 Starlette/FastAPI 框架错误。"""

        return error_response(
            code="HTTP_ERROR",
            message=str(exc.detail),
            status_code=exc.status_code,
            request_id=get_request_id(request),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception):
        """未知异常兜底，避免内部堆栈或数据库细节直接暴露给客户端。"""

        return error_response(
            code="INTERNAL_SERVER_ERROR",
            message="服务器内部错误",
            status_code=500,
            request_id=get_request_id(request),
            details={"error": exc.__class__.__name__},
        )
