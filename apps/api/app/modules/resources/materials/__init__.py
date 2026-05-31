# app/modules/resources/materials/__init__.py
"""
物资资源能力模块

对外导出物资台账、分类和库存维护服务，供 HTTP 接口和借用域复用。
"""

from app.modules.resources.materials.service import (
    adjust_material_stock,
    create_material,
    create_resource_category,
    get_material,
    list_materials,
    list_resource_categories,
    update_material,
)

__all__ = [
    "adjust_material_stock",
    "create_material",
    "create_resource_category",
    "get_material",
    "list_materials",
    "list_resource_categories",
    "update_material",
]
