# app/core/errors/codes.py
"""
稳定错误码注册表

本文件收敛需要被端侧和文档稳定识别的错误码。业务层仍然可以直接抛出
`AppError("SOME_CODE", "...")`，但核心错误码应逐步进入这里，避免端侧解析中文
message，也方便后续生成错误码文档。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ErrorCode(StrEnum):
    """端侧可识别的稳定错误码。"""

    # --- 通用与认证 ---
    VALIDATION_ERROR = "VALIDATION_ERROR"
    INTERNAL_SERVER_ERROR = "INTERNAL_SERVER_ERROR"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    AUTH_HEADER_MISSING = "AUTH_HEADER_MISSING"
    AUTH_HEADER_INVALID = "AUTH_HEADER_INVALID"
    INVALID_ACCESS_TOKEN = "INVALID_ACCESS_TOKEN"
    AUTH_SESSION_REVOKED = "AUTH_SESSION_REVOKED"
    AUTH_SESSION_NOT_FOUND = "AUTH_SESSION_NOT_FOUND"
    AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"

    # --- 组织与成员 ---
    MEMBER_PROFILE_PHONE_INVALID = "MEMBER_PROFILE_PHONE_INVALID"
    MEMBER_PROFILE_EMAIL_INVALID = "MEMBER_PROFILE_EMAIL_INVALID"

    # --- 资源与借用 ---
    MATERIAL_NOT_FOUND = "MATERIAL_NOT_FOUND"
    BORROW_APPLICATION_NOT_FOUND = "BORROW_APPLICATION_NOT_FOUND"
    BORROW_APPLICATION_FORBIDDEN = "BORROW_APPLICATION_FORBIDDEN"
    BORROW_PROFILE_INCOMPLETE = "BORROW_PROFILE_INCOMPLETE"
    BORROW_DEPOSIT_NOT_ENOUGH = "BORROW_DEPOSIT_NOT_ENOUGH"
    BORROW_MATERIAL_STOCK_NOT_ENOUGH = "BORROW_MATERIAL_STOCK_NOT_ENOUGH"
    BORROW_APPLICATION_NOT_EDITABLE = "BORROW_APPLICATION_NOT_EDITABLE"


@dataclass(frozen=True)
class ErrorSpec:
    """错误码元数据。"""

    code: ErrorCode
    status_code: int
    message: str
    domain: str


ERROR_SPECS: dict[ErrorCode, ErrorSpec] = {
    ErrorCode.VALIDATION_ERROR: ErrorSpec(
        code=ErrorCode.VALIDATION_ERROR,
        status_code=422,
        message="请求参数不合法",
        domain="shared",
    ),
    ErrorCode.PERMISSION_DENIED: ErrorSpec(
        code=ErrorCode.PERMISSION_DENIED,
        status_code=403,
        message="当前用户无权执行该操作",
        domain="permissions",
    ),
    ErrorCode.MATERIAL_NOT_FOUND: ErrorSpec(
        code=ErrorCode.MATERIAL_NOT_FOUND,
        status_code=404,
        message="物资不存在",
        domain="resources",
    ),
    ErrorCode.BORROW_APPLICATION_NOT_FOUND: ErrorSpec(
        code=ErrorCode.BORROW_APPLICATION_NOT_FOUND,
        status_code=404,
        message="借用申请不存在",
        domain="borrowing",
    ),
    ErrorCode.BORROW_APPLICATION_FORBIDDEN: ErrorSpec(
        code=ErrorCode.BORROW_APPLICATION_FORBIDDEN,
        status_code=403,
        message="只能查看自己的借用申请",
        domain="borrowing",
    ),
    ErrorCode.BORROW_PROFILE_INCOMPLETE: ErrorSpec(
        code=ErrorCode.BORROW_PROFILE_INCOMPLETE,
        status_code=422,
        message="成员资料不完整",
        domain="borrowing",
    ),
    ErrorCode.BORROW_DEPOSIT_NOT_ENOUGH: ErrorSpec(
        code=ErrorCode.BORROW_DEPOSIT_NOT_ENOUGH,
        status_code=409,
        message="可用积分不足",
        domain="borrowing",
    ),
    ErrorCode.BORROW_MATERIAL_STOCK_NOT_ENOUGH: ErrorSpec(
        code=ErrorCode.BORROW_MATERIAL_STOCK_NOT_ENOUGH,
        status_code=409,
        message="物资可借库存不足",
        domain="borrowing",
    ),
    ErrorCode.BORROW_APPLICATION_NOT_EDITABLE: ErrorSpec(
        code=ErrorCode.BORROW_APPLICATION_NOT_EDITABLE,
        status_code=409,
        message="申请当前不能修改",
        domain="borrowing",
    ),
}


def normalize_error_code(code: ErrorCode | str) -> str:
    """把错误码枚举或字符串规范化为响应中的字符串 code。"""

    return code.value if isinstance(code, ErrorCode) else code


def get_error_spec(code: ErrorCode | str) -> ErrorSpec | None:
    """读取已登记错误码元数据，未登记时返回 None。"""

    if isinstance(code, ErrorCode):
        return ERROR_SPECS.get(code)
    try:
        return ERROR_SPECS.get(ErrorCode(code))
    except ValueError:
        return None
