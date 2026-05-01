# app/core/security/middleware.py
"""
HTTP 安全边界中间件

本文件集中放置所有接口都会经过的轻量安全防护：安全响应头、请求体大小限制和
基础限流。它们不能替代网关、WAF、Redis 限流或对象存储配额，但可以让本地、
预发布和单实例部署默认具备明确的底线。
"""

from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from time import monotonic
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.shared.request_context import REQUEST_ID_HEADER
from app.shared.responses import error_response


def ensure_request_id(request: Request) -> str:
    """
    读取或创建 request_id。

    正常情况下 RequestContextMiddleware 会先写入 request.state.request_id；如果安全
    中间件在更外层直接拒绝请求，这里兜底生成同样格式的 ID，保证响应仍可追踪。
    """

    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id

    request_id = f"req_{uuid4().hex}"
    request.state.request_id = request_id
    return request_id


def get_client_ip(request: Request) -> str:
    """
    获取限流使用的客户端地址。

    当前只使用 ASGI server 解析出的 client host，不信任 X-Forwarded-For。
    如果后续部署在可信反向代理后，需要先在网关和 Uvicorn proxy headers 上统一配置。
    """

    if request.client is None:
        return "-"
    return request.client.host


def path_matches(path: str, patterns: list[str]) -> bool:
    """
    判断路径是否匹配配置列表。

    配置项默认按精确匹配；以 `*` 结尾时作为前缀匹配，用于后续扩展一组路由。
    """

    for pattern in patterns:
        if pattern.endswith("*") and path.startswith(pattern[:-1]):
            return True
        if path == pattern:
            return True
    return False


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """
    统一写入安全响应头。

    这些头主要降低 MIME sniffing、clickjacking、referrer 泄露和浏览器特性滥用风险。
    HSTS 默认只在 production 开启，避免本地 HTTP 开发被浏览器强制升级。
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        hsts_enabled: bool,
        hsts_max_age_seconds: int,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.hsts_enabled = hsts_enabled
        self.hsts_max_age_seconds = hsts_max_age_seconds

    async def dispatch(self, request: Request, call_next) -> Response:
        """在响应返回前补齐安全头。"""

        response = await call_next(request)
        if not self.enabled:
            return response

        self._set_default(response, "X-Content-Type-Options", "nosniff")
        self._set_default(response, "X-Frame-Options", "DENY")
        self._set_default(response, "Referrer-Policy", "strict-origin-when-cross-origin")
        self._set_default(response, "Cross-Origin-Resource-Policy", "same-site")
        self._set_default(response, "X-XSS-Protection", "0")
        self._set_default(
            response,
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        if self.hsts_enabled:
            self._set_default(
                response,
                "Strict-Transport-Security",
                f"max-age={self.hsts_max_age_seconds}; includeSubDomains",
            )

        return response

    @staticmethod
    def _set_default(response: Response, name: str, value: str) -> None:
        """只在下游未设置时写入默认安全头。"""

        if name not in response.headers:
            response.headers[name] = value


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """
    基于 Content-Length 的请求体大小限制。

    该中间件先挡住显式超大请求，避免普通 JSON 接口被大 body 消耗资源。后续文件上传
    应使用专门的上传接口、预签名 URL 和对象存储配额，不应放宽全局限制。
    """

    def __init__(self, app, *, enabled: bool, max_body_bytes: int) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.max_body_bytes = max_body_bytes

    async def dispatch(self, request: Request, call_next) -> Response:
        """检查 Content-Length，超过限制时直接返回 413。"""

        if not self.enabled:
            return await call_next(request)

        content_length = request.headers.get("content-length")
        if content_length is not None:
            try:
                request_size = int(content_length)
            except ValueError:
                request_size = self.max_body_bytes + 1

            if request_size > self.max_body_bytes:
                request_id = ensure_request_id(request)
                response = error_response(
                    code="REQUEST_BODY_TOO_LARGE",
                    message="请求体过大",
                    status_code=413,
                    request_id=request_id,
                    details={"max_body_bytes": self.max_body_bytes},
                )
                response.headers[REQUEST_ID_HEADER] = request_id
                return response

        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    进程内固定窗口限流。

    这是应用层兜底防护，适合本地开发、测试和单实例小流量部署。多进程或多实例生产环境
    仍应使用网关、Redis 或云厂商限流；这里保留相同错误码和响应头，方便未来替换实现。
    """

    def __init__(
        self,
        app,
        *,
        enabled: bool,
        exempt_paths: list[str],
        sensitive_paths: list[str],
        default_window_seconds: int,
        default_max_requests: int,
        sensitive_window_seconds: int,
        sensitive_max_requests: int,
    ) -> None:
        super().__init__(app)
        self.enabled = enabled
        self.exempt_paths = exempt_paths
        self.sensitive_paths = sensitive_paths
        self.default_window_seconds = default_window_seconds
        self.default_max_requests = default_max_requests
        self.sensitive_window_seconds = sensitive_window_seconds
        self.sensitive_max_requests = sensitive_max_requests
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()
        self._last_pruned_at = 0.0

    async def dispatch(self, request: Request, call_next) -> Response:
        """执行限流判断。"""

        if not self.enabled or path_matches(request.url.path, self.exempt_paths):
            return await call_next(request)

        bucket = "auth" if path_matches(request.url.path, self.sensitive_paths) else "global"
        limit, window = self._get_limit(bucket)
        client_ip = get_client_ip(request)
        allowed, remaining, retry_after = await self._consume(
            key=f"{bucket}:{client_ip}",
            limit=limit,
            window_seconds=window,
        )
        if allowed:
            response = await call_next(request)
            response.headers["X-RateLimit-Limit"] = str(limit)
            response.headers["X-RateLimit-Remaining"] = str(remaining)
            return response

        request_id = ensure_request_id(request)
        response = error_response(
            code="RATE_LIMIT_EXCEEDED",
            message="请求过于频繁，请稍后再试",
            status_code=429,
            request_id=request_id,
            details={"bucket": bucket, "retry_after": retry_after},
        )
        response.headers[REQUEST_ID_HEADER] = request_id
        response.headers["Retry-After"] = str(retry_after)
        response.headers["X-RateLimit-Limit"] = str(limit)
        response.headers["X-RateLimit-Remaining"] = "0"
        return response

    def _get_limit(self, bucket: str) -> tuple[int, int]:
        """根据限流桶返回最大请求数和窗口秒数。"""

        if bucket == "auth":
            return self.sensitive_max_requests, self.sensitive_window_seconds
        return self.default_max_requests, self.default_window_seconds

    async def _consume(
        self,
        *,
        key: str,
        limit: int,
        window_seconds: int,
    ) -> tuple[bool, int, int]:
        """消费一次请求额度。"""

        now = monotonic()
        cutoff = now - window_seconds

        async with self._lock:
            if now - self._last_pruned_at >= min(
                self.default_window_seconds,
                self.sensitive_window_seconds,
            ):
                self._prune_expired_events(now)

            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()

            if len(events) >= limit:
                retry_after = max(1, int(window_seconds - (now - events[0])))
                return False, 0, retry_after

            events.append(now)
            remaining = max(0, limit - len(events))
            return True, remaining, 0

    def _prune_expired_events(self, now: float) -> None:
        """清理已经过期且为空的限流窗口，避免长时间运行后 key 无限增长。"""

        for key, events in list(self._events.items()):
            window = self.sensitive_window_seconds if key.startswith("auth:") else self.default_window_seconds
            cutoff = now - window
            while events and events[0] <= cutoff:
                events.popleft()
            if not events:
                del self._events[key]
        self._last_pruned_at = now
