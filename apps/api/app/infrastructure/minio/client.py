from __future__ import annotations

import asyncio
from minio import Minio

from app.core.config.settings import get_settings


def create_minio_client() -> Minio:
    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def ping_minio() -> None:
    settings = get_settings()
    client = create_minio_client()
    await asyncio.to_thread(client.bucket_exists, settings.minio_public_bucket)
