# app/modules/resources/constants.py
"""
资源域常量

资源域只维护物资、场地、工位等可借用对象的基础资料、库存和状态。借用申请、
审批、归还与押金不在这里处理，避免资源台账和借用生命周期互相污染。
"""

# --- 资源类型 ---
RESOURCE_TYPE_MATERIAL = "material"
RESOURCE_TYPE_SITE = "site"
RESOURCE_TYPE_WORKSTATION = "workstation"

# --- 资源分类状态 ---
RESOURCE_CATEGORY_ACTIVE = "active"
RESOURCE_CATEGORY_DISABLED = "disabled"

# --- 物资状态 ---
MATERIAL_STATUS_AVAILABLE = "available"
MATERIAL_STATUS_MAINTENANCE = "maintenance"
MATERIAL_STATUS_DISABLED = "disabled"
MATERIAL_STATUS_RETIRED = "retired"

MATERIAL_ACTIVE_STATUSES = {
    MATERIAL_STATUS_AVAILABLE,
    MATERIAL_STATUS_MAINTENANCE,
    MATERIAL_STATUS_DISABLED,
    MATERIAL_STATUS_RETIRED,
}
