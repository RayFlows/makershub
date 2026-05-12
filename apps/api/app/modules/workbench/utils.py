# app/modules/workbench/utils.py
"""
工作台校验与规范化工具

这些函数只处理任务域内部常用的短文本、状态和可选说明校验。跨域规则，例如用户是否
存在、积分规则是否可用、协会身份是否能领取任务，仍放在服务层显式处理。
"""

from __future__ import annotations

from app.core.errors import AppError


def normalize_required_text(value: str, *, field_label: str, max_length: int = 500) -> str:
    """清理必填文本。"""

    normalized = value.strip()
    if not normalized:
        raise AppError("WORKBENCH_FIELD_REQUIRED", f"{field_label}不能为空", status_code=422)
    if len(normalized) > max_length:
        raise AppError("WORKBENCH_FIELD_TOO_LONG", f"{field_label}过长", status_code=422)
    return normalized


def normalize_optional_text(
    value: str | None,
    *,
    field_label: str,
    max_length: int = 500,
) -> str | None:
    """清理可选文本。"""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise AppError("WORKBENCH_FIELD_TOO_LONG", f"{field_label}过长", status_code=422)
    return normalized
