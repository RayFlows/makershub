# app/shared/request_context.py
"""
请求上下文中间件

为每个请求生成或透传 X-Request-ID，并写入 request.state。
统一 request_id 后，前端报错、API 响应和后端日志可以对齐到同一次请求。
"""

from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import Request
from loguru import logger
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
        started_at = perf_counter()
        client_ip = request.client.host if request.client else "-"
        query = f"?{request.url.query}" if request.url.query else ""

        with logger.contextualize(request_id=request_id):
            # 请求日志只记录路由、来源和耗时，不读取 body，避免敏感字段进入日志。
            logger.info(
                "HTTP 请求开始 | method={} path={}{} client_ip={}",
                request.method,
                request.url.path,
                query,
                client_ip,
            )
            try:
                response = await call_next(request)
            except Exception:
                duration_ms = (perf_counter() - started_at) * 1000
                logger.exception(
                    "HTTP 请求异常 | method={} path={} duration_ms={:.2f}",
                    request.method,
                    request.url.path,
                    duration_ms,
                )
                raise

            duration_ms = (perf_counter() - started_at) * 1000
            response.headers[REQUEST_ID_HEADER] = request_id
            logger.info(
                "HTTP 请求结束 | method={} path={} status={} duration_ms={:.2f}",
                request.method,
                request.url.path,
                response.status_code,
                duration_ms,
            )
            return response


def get_request_id(request: Request) -> str:
    """从请求上下文中读取 request_id。

    理论上中间件会提前写入 request.state.request_id；兜底生成是为了在测试或
    非标准调用路径中仍然能返回统一响应结构。
    """

    return getattr(request.state, "request_id", f"req_{uuid4().hex}")
