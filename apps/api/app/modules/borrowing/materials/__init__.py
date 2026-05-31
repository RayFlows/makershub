# app/modules/borrowing/materials/__init__.py
"""
物资借用能力模块

对外导出物资借用申请、审批、取消和归还服务。
"""

from app.modules.borrowing.materials.service import (
    cancel_material_borrow_application,
    create_material_borrow_application,
    get_applicant_current_contact,
    get_material_borrow_application,
    list_material_borrow_applications,
    return_material_borrow_application,
    review_material_borrow_application,
)

__all__ = [
    "cancel_material_borrow_application",
    "create_material_borrow_application",
    "get_applicant_current_contact",
    "get_material_borrow_application",
    "list_material_borrow_applications",
    "return_material_borrow_application",
    "review_material_borrow_application",
]
