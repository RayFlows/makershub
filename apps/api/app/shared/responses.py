# app/shared/responses.py
"""
统一响应结构

项目所有 HTTP 接口都应该返回 success/data/message/request_id 或
success/error/request_id 的统一结构。这样前端、小程序和后台管理端可以复用同一套
API 客户端和错误处理逻辑。
"""

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
    """
    构造成功响应。

    Args:
        data: 业务数据，可以是字典、列表、分页对象或 None。
        message: 人类可读的简短提示，默认 ok。
        request_id: 当前请求 ID，由 RequestContextMiddleware 提供。
        status_code: HTTP 状态码，默认 200。

    Returns:
        Starlette JSONResponse 对象。
    """

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
    """
    构造失败响应。

    Args:
        code: 稳定错误码，前端应优先识别该字段。
        message: 人类可读错误信息。
        status_code: HTTP 状态码。
        request_id: 当前请求 ID。
        details: 可选调试细节，生产环境不要放敏感信息。

    Returns:
        Starlette JSONResponse 对象。
    """

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
