from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config.settings import get_settings


settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    docs_url=f"{settings.api_prefix}/docs",
    openapi_url=f"{settings.api_prefix}/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allow_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": settings.app_name,
        "env": settings.app_env,
    }


@app.get(f"{settings.api_prefix}/health", tags=["system"])
async def api_health() -> dict[str, object]:
    return {
        "code": 0,
        "message": "ok",
        "data": {
            "status": "ok",
            "service": settings.app_name,
            "env": settings.app_env,
        },
    }
