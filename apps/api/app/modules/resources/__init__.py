# app/modules/resources/__init__.py
"""
资源业务域

资源域负责物资、场地、工位等可借用对象的基础台账和库存状态。
"""

from app.modules.resources.models import Material, ResourceCategory

__all__ = ["Material", "ResourceCategory"]
