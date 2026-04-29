# app/interfaces/http/__init__.py
"""
HTTP 接口层

interfaces/http 只负责协议层适配，例如路由、请求模型、响应模型和依赖注入。
核心业务规则应放在 modules 下，避免接口层和业务层互相缠绕。
"""
