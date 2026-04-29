# app/main.py
"""
MakersHub API 主应用入口

本文件负责组装 FastAPI 应用，包括生命周期、跨域、中间件、异常处理和 V1 路由注册。
业务规则不直接写在 main.py 中，避免应用入口随着业务增长变成“上帝文件”。

主要功能:
1. 创建 FastAPI 应用实例；
2. 注册 CORS 和请求上下文中间件；
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
from app.interfaces.http.v1 import api_router
from app.shared.request_context import RequestContextMiddleware, get_request_id
from app.shared.responses import success_response


settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI 生命周期管理。

    Args:
        app: 当前 FastAPI 应用实例。当前暂不直接使用，但保留参数以符合框架签名。

    注意:
        启动阶段暂不自动建表，数据库结构必须通过 Alembic 迁移管理。
        关闭阶段释放数据库连接池，避免容器停止或测试进程退出时留下悬挂连接。
    """

    yield
    await close_database_engine()


def create_app() -> FastAPI:
    """
    创建并配置 FastAPI 应用。

    Returns:
        已注册中间件、异常处理和路由的 FastAPI 实例。
    """

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
