# app/modules/organization/__init__.py
"""
组织与成员模块导出

organization 负责职务、部门、成员关系等组织结构数据。
登录凭证属于 identity，业务权限点后续会拆到 permission/authorization 能力中。
"""

from app.modules.organization.models import Position, UserPosition

__all__ = ["Position", "UserPosition"]
