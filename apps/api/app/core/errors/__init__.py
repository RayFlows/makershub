# app/core/errors/__init__.py
"""
统一错误处理导出

业务层抛出 AppError，应用入口注册 register_exception_handlers，
最终所有错误响应都收敛到统一 JSON 格式。
"""

from app.core.errors.codes import ERROR_SPECS, ErrorCode, ErrorSpec
from app.core.errors.exceptions import AppError
from app.core.errors.handlers import register_exception_handlers

__all__ = ["ERROR_SPECS", "AppError", "ErrorCode", "ErrorSpec", "register_exception_handlers"]
