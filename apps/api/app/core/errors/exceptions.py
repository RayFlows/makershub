# app/core/errors/exceptions.py
"""
应用内部错误类型

业务代码只抛出 AppError，由统一异常处理器转换成标准响应。
这样可以避免在服务层到处拼 HTTPException，也方便后续接入错误码文档和审计日志。
"""

from __future__ import annotations

from typing import Any

from app.core.errors.codes import ErrorCode, get_error_spec, normalize_error_code


class AppError(Exception):
    """可被客户端识别的业务异常。

    code 用于前端和文档稳定识别错误类型，message 用于展示或调试。
    status_code 只表达 HTTP 语义，不应该承担业务权限判断。
    """

    def __init__(
        self,
        code: ErrorCode | str,
        message: str | None = None,
        *,
        status_code: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        spec = get_error_spec(code)
        self.code = normalize_error_code(code)
        self.message = message or (spec.message if spec is not None else "业务处理失败")
        self.status_code = status_code or (spec.status_code if spec is not None else 400)
        self.details = details or {}
        super().__init__(self.message)
