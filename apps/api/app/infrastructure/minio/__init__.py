# app/infrastructure/minio/__init__.py
"""
MinIO 基础设施适配导出

业务模块不直接创建 MinIO 客户端，统一通过 infrastructure 层隔离对象存储实现。
"""

from app.infrastructure.minio.client import ping_minio

__all__ = ["ping_minio"]
