# app/modules/organization/departments/__init__.py
"""
部门能力导出
"""

from app.modules.organization.departments.service import assign_member_department, list_active_departments

__all__ = ["assign_member_department", "list_active_departments"]
