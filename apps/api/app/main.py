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
    yield
    await close_database_engine()


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        docs_url=f"{settings.api_prefix}/docs",
        openapi_url=f"{settings.api_prefix}/openapi.json",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allow_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(RequestContextMiddleware)

    register_exception_handlers(app)
    app.include_router(api_router, prefix=settings.api_prefix)

    @app.get("/health", tags=["system"])
    async def liveness(request: Request):
        return success_response(
            {
                "status": "ok",
                "service": settings.app_name,
                "env": settings.app_env,
            },
            request_id=get_request_id(request),
        )

    return app


app = create_app()
