# app/shared/schemas/__init__.py
"""
共享 Schema 包

这里预留跨业务域复用的 Pydantic 模型，例如分页结构、文件摘要、审计上下文等。
具体接口 schema 仍优先放在各自 HTTP 模块中，避免共享包变成杂物箱。
"""
