from __future__ import annotations

from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

REQUEST_ID_HEADER = "X-Request-ID"


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or f"req_{uuid4().hex}"
        request.state.request_id = request_id

        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


def get_request_id(request: Request) -> str:
    return getattr(request.state, "request_id", f"req_{uuid4().hex}")
