# app/modules/organization/utils.py
"""
组织域字段规范化工具

本文件集中处理成员资料、用户主体字段和职务 code 的输入清理。接口层只负责 HTTP
契约，真正的业务字段规则应该留在组织域内部。
"""

from __future__ import annotations

import re
from typing import TypeVar

from app.core.errors import AppError

ItemT = TypeVar("ItemT")


def normalize_member_profile_update(payload: dict[str, str | None]) -> dict[str, str | None]:
    """
    规范化成员资料更新内容。

    空字符串会转为 None，避免数据库里长期保存不可见空白。
    """

    normalizers = {
        "real_name": lambda value: normalize_optional_text(value, max_length=100, field_label="真实姓名"),
        "student_id": lambda value: normalize_digits(value, max_length=32, field_label="学号"),
        "phone": normalize_phone,
        "email": normalize_contact_email,
        "college": lambda value: normalize_optional_text(value, max_length=100, field_label="学院"),
        "major": lambda value: normalize_optional_text(value, max_length=100, field_label="专业"),
        "grade": lambda value: normalize_digits(value, max_length=20, field_label="年级"),
        "qq": lambda value: normalize_digits(value, max_length=20, field_label="QQ"),
        "bio": lambda value: normalize_optional_text(value, max_length=500, field_label="个人简介"),
    }
    return {field: normalizers[field](value) for field, value in payload.items() if field in normalizers}


def normalize_member_user_update(payload: dict[str, str | None]) -> dict[str, str | None]:
    """规范化后台可维护的用户主体字段。"""

    update_data: dict[str, str | None] = {}
    if "display_name" in payload:
        display_name = normalize_optional_text(
            payload["display_name"],
            max_length=80,
            field_label="展示名",
        )
        if display_name is None:
            raise AppError("USER_DISPLAY_NAME_REQUIRED", "展示名不能为空", status_code=422)
        update_data["display_name"] = display_name

    if "status" in payload:
        status = normalize_optional_text(payload["status"], max_length=32, field_label="用户状态")
        if status not in {"active", "disabled"}:
            raise AppError("USER_STATUS_INVALID", "用户状态只能为 active 或 disabled", status_code=422)
        update_data["status"] = status

    if "remark" in payload:
        update_data["remark"] = normalize_optional_text(
            payload["remark"],
            max_length=500,
            field_label="备注",
        )

    return update_data


def normalize_optional_text(value: str | None, *, max_length: int, field_label: str) -> str | None:
    """清理可选文本字段，并检查长度。"""

    if value is None:
        return None
    normalized = value.strip()
    if not normalized:
        return None
    if len(normalized) > max_length:
        raise AppError("MEMBER_PROFILE_FIELD_TOO_LONG", f"{field_label}过长", status_code=422)
    return normalized


def normalize_digits(value: str | None, *, max_length: int, field_label: str) -> str | None:
    """清理必须由数字组成的可选字段。"""

    normalized = normalize_optional_text(value, max_length=max_length, field_label=field_label)
    if normalized is None:
        return None
    if not normalized.isdigit():
        raise AppError("MEMBER_PROFILE_FIELD_INVALID", f"{field_label}必须由数字组成", status_code=422)
    return normalized


def normalize_phone(value: str | None) -> str | None:
    """
    清理手机号字段。

    当前先按中国大陆常见 11 位手机号校验，和旧小程序编辑页的校验保持一致。
    """

    normalized = normalize_optional_text(value, max_length=20, field_label="手机号")
    if normalized is None:
        return None
    if not re.fullmatch(r"1[3-9]\d{9}", normalized):
        raise AppError("MEMBER_PROFILE_PHONE_INVALID", "手机号格式不正确", status_code=422)
    return normalized


def normalize_contact_email(value: str | None) -> str | None:
    """清理联系邮箱字段。"""

    normalized = normalize_optional_text(value, max_length=255, field_label="联系邮箱")
    if normalized is None:
        return None
    normalized = normalized.lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", normalized):
        raise AppError("MEMBER_PROFILE_EMAIL_INVALID", "联系邮箱格式不正确", status_code=422)
    return normalized


def normalize_position_codes(position_codes: list[str]) -> list[str]:
    """清理职务 code 列表，并保持调用方传入顺序。"""

    normalized_codes: list[str] = []
    seen: set[str] = set()
    for code in position_codes:
        normalized = code.strip()
        if not normalized:
            raise AppError("POSITION_CODE_INVALID", "职务 code 不能为空", status_code=422)
        if normalized in seen:
            continue
        normalized_codes.append(normalized)
        seen.add(normalized)
    return normalized_codes


def group_by_user_id(items: list[ItemT]) -> dict[int, list[ItemT]]:
    """按 user_id 对部门关系或职务关系分组。"""

    grouped: dict[int, list[ItemT]] = {}
    for item in items:
        grouped.setdefault(item.user_id, []).append(item)
    return grouped
