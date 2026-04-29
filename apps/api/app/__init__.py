# app/__init__.py
"""
MakersHub API 应用包

该包是后端服务的主代码入口，内部按工程分层拆分为:
1. core: 配置、数据库、安全、错误处理等基础能力；
2. interfaces: HTTP/API 等对外入口；
3. modules: 按业务域组织的核心业务代码；
4. infrastructure: MinIO、第三方服务等基础设施适配；
5. shared: 跨模块复用的小型工具和响应结构。
"""
