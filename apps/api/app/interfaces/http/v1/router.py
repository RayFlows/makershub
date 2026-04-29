# app/interfaces/http/v1/router.py
"""
V1 API 总路由

每个业务域在自己的 router 文件中声明路由，最后统一挂载到 api_router。
这样 main.py 只需要 include 一个总路由，模块增加时不会让应用入口越来越臃肿。
"""

from fastapi import APIRouter

from app.interfaces.http.v1.auth.router import router as auth_router
from app.interfaces.http.v1.system.router import router as system_router

# --- V1 路由聚合 ---
api_router = APIRouter()
api_router.include_router(auth_router, tags=["auth"])  # 身份登录、令牌和当前用户接口
api_router.include_router(system_router, tags=["system"])  # 系统健康检查和基础探活接口
