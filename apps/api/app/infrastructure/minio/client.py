# app/infrastructure/minio/client.py
"""
MinIO 客户端与健康检查

本地开发、预发布和生产都通过 S3 兼容协议访问对象存储。
该模块只负责创建客户端和检查可用性，不承载具体文件上传、权限或业务归档规则。
"""

from __future__ import annotations

import asyncio

from minio import Minio

from app.core.config.settings import get_settings


def create_minio_client() -> Minio:
    """
    创建 MinIO 客户端。

    Returns:
        已根据运行时配置初始化的 MinIO 客户端。
    """

    settings = get_settings()
    return Minio(
        settings.minio_endpoint,
        access_key=settings.minio_access_key,
        secret_key=settings.minio_secret_key,
        secure=settings.minio_secure,
    )


async def ping_minio() -> None:
    """
    MinIO 健康检查。

    MinIO SDK 是同步客户端，因此通过 asyncio.to_thread 放到线程池执行，
    避免阻塞 FastAPI 事件循环。
    """

    settings = get_settings()
    client = create_minio_client()
    await asyncio.to_thread(client.bucket_exists, settings.minio_public_bucket)
