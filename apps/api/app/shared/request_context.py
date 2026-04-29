# app/shared/request_context.py
"""
请求上下文中间件

为每个请求生成或透传 X-Request-ID，并写入 request.state。
统一 request_id 后，前端报错、API 响应和后端日志可以对齐到同一次请求。
"""

from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    """请求 ID 中间件。

    如果客户端已经传入 X-Request-ID，则沿用该值；否则后端生成 req_ 前缀的 ID。
    响应头中始终回写同一个 ID，方便客户端记录。
    """

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex}"
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def get_request_id(request: Request) -> str:
    """从请求上下文中读取 request_id。

    理论上中间件会提前写入 request.state.request_id；兜底生成是为了在测试或
    非标准调用路径中仍然能返回统一响应结构。
    """

    return getattr(request.state, "request_id", f"req_{uuid4().hex}")
