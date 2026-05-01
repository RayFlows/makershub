# app/main.py
"""
MakersHub API 主应用入口

本文件负责组装 FastAPI 应用，包括生命周期、跨域、中间件、异常处理和 V1 路由注册。
业务规则不直接写在 main.py 中，避免应用入口随着业务增长变成“上帝文件”。

主要功能:
1. 创建 FastAPI 应用实例；
2. 注册 CORS、安全边界和请求上下文中间件；
3. 注册统一异常处理器；
4. 挂载 /api/v1 路由；
5. 提供进程级 liveness 健康检查；
6. 应用关闭时释放数据库连接池。
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.settings import get_settings
from app.core.database import close_database_engine
from app.core.errors import register_exception_handlers
from app.core.logging import logger, setup_logging
from app.core.security import (
    RateLimitMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)
from app.interfaces.http.v1 import api_router
from app.shared.request_context import RequestContextMiddleware, get_request_id
from app.shared.responses import success_response


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """
    FastAPI 生命周期管理。

    Args:
        _app: 当前 FastAPI 应用实例。当前暂不直接使用，但保留参数以符合框架签名。

    注意:
        启动阶段暂不自动建表，数据库结构必须通过 Alembic 迁移管理。
        关闭阶段释放数据库连接池，避免容器停止或测试进程退出时留下悬挂连接。
    """

    settings = get_settings()
    logger.info("应用启动完成 | env={} api_prefix={}", settings.app_env, settings.api_prefix)
    yield
    logger.info("应用准备关闭")
    await close_database_engine()
    logger.info("数据库连接池已关闭")


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用。

    Returns:
        已注册中间件、异常处理和路由的 FastAPI 实例。
    """

    # --- 日志初始化 ---
    settings = get_settings()
    setup_logging()
    logger.info("日志系统初始化完成 | env={} level={}", settings.app_env, settings.log_level)

    # --- 应用实例 ---
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    # --- 中间件注册 ---
    # CORS 允许本地 web/admin/docs 三个前端入口访问 API。
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(
        SecurityHeadersMiddleware,
        enabled=settings.security_headers_enabled,
        hsts_enabled=settings.should_send_hsts_header,
        hsts_max_age_seconds=settings.hsts_max_age_seconds,
    )
    app.add_middleware(
        RequestSizeLimitMiddleware,
        enabled=settings.request_size_limit_enabled,
        max_body_bytes=settings.max_request_body_bytes,
    )
    app.add_middleware(
        RateLimitMiddleware,
        enabled=settings.rate_limit_enabled,
        exempt_paths=settings.rate_limit_exempt_path_list,
        sensitive_paths=settings.auth_rate_limit_path_list,
        default_window_seconds=settings.rate_limit_window_seconds,
        default_max_requests=settings.rate_limit_max_requests,
        sensitive_window_seconds=settings.auth_rate_limit_window_seconds,
        sensitive_max_requests=settings.auth_rate_limit_max_requests,
    )
    # RequestContextMiddleware 必须尽早注册，保证后续异常响应也能拿到 request_id。
    app.add_middleware(RequestContextMiddleware)

    # --- 异常处理与路由注册 ---
    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["system"])
    async def liveness(request: Request):
        """
        进程存活检查。

        该接口只证明 API 进程还活着，不检查数据库和 MinIO。
        部署平台可以用它做轻量 liveness probe，完整依赖检查请使用 /api/v1/health。
        """

        return success_response(
            {
                "status": "ok",
                "service": settings.app_name,
                "env": settings.app_env,
            },
            request_id=get_request_id(request),
        )

    return app


# --- ASGI 应用实例 ---
# Uvicorn/Docker 通过 app.main:app 加载该对象。
app = create_app()
