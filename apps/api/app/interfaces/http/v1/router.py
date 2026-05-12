# app/interfaces/http/v1/router.py
"""
V1 API 总路由

每个业务域在自己的 router 文件中声明路由，最后统一挂载到 api_router。
这样 main.py 只需要 include 一个总路由，模块增加时不会让应用入口越来越臃肿。
"""

from fastapi import APIRouter

from app.interfaces.http.v1.audit.router import router as audit_router
from app.interfaces.http.v1.auth.router import router as auth_router
from app.interfaces.http.v1.files.router import router as files_router
from app.interfaces.http.v1.organization.router import router as organization_router
from app.interfaces.http.v1.permissions.router import router as permissions_router
from app.interfaces.http.v1.points.router import router as points_router
from app.interfaces.http.v1.system.router import router as system_router

# --- V1 路由聚合 ---
api_router = APIRouter()
api_router.include_router(audit_router, tags=["audit"])  # 审计日志读取接口
api_router.include_router(auth_router, tags=["auth"])  # 身份登录、令牌和当前用户接口
api_router.include_router(files_router, tags=["files"])  # 统一文件上传入口
api_router.include_router(organization_router, tags=["organization"])  # 组织、部门和成员资料接口
api_router.include_router(permissions_router, tags=["permissions"])  # 权限点和当前用户权限摘要
api_router.include_router(points_router, tags=["points"])  # 积分账户、流水和受控人工调整接口
api_router.include_router(system_router, tags=["system"])  # 系统健康检查和基础探活接口
