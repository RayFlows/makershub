# app/interfaces/http/v1/__init__.py
"""
V1 API 路由导出

第一阶段正式接口统一挂在 /api/v1 下。
后续如果出现 V2，不应破坏这里的已有契约。
"""

from app.interfaces.http.v1.router import api_router

__all__ = ["api_router"]
