# app/modules/resources/materials/service.py
"""
物资资源服务

本文件维护物资分类、物资基础资料和库存数值。旧系统审批借用时直接操作 `stuffs`，
新版保留这一库存语义，但所有库存变化都集中在这里，方便审计、测试和后续扩展库存日志。
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import AppError
from app.modules.resources.constants import (
    MATERIAL_ACTIVE_STATUSES,
    MATERIAL_STATUS_AVAILABLE,
    RESOURCE_CATEGORY_ACTIVE,
    RESOURCE_TYPE_MATERIAL,
)
from app.modules.resources.materials.repository import MaterialRepository
from app.modules.resources.models import Material, ResourceCategory
from app.modules.resources.types import MaterialPage, ResourceCategoryPage
from app.modules.resources.utils import (
    ensure_available_not_greater_than_total,
    normalize_non_negative_int,
    normalize_optional_text,
    normalize_required_text,
)


# --- 资源分类 ---
async def create_resource_category(
    session: AsyncSession,
    *,
    name: str,
    sort_order: int = 0,
    status: str = RESOURCE_CATEGORY_ACTIVE,
) -> ResourceCategory:
    """创建物资分类。"""

    normalized_name = normalize_required_text(name, field_label="分类名称", max_length=120)
    normalized_status = normalize_required_text(status, field_label="分类状态", max_length=32)
    if normalized_status not in {RESOURCE_CATEGORY_ACTIVE, "disabled"}:
        raise AppError("RESOURCE_CATEGORY_STATUS_INVALID", "资源分类状态不合法", status_code=422)

    category = ResourceCategory(
        name=normalized_name,
        resource_type=RESOURCE_TYPE_MATERIAL,
        status=normalized_status,
        sort_order=sort_order,
    )
    repository = MaterialRepository(session)
    return await repository.add_category(category)


async def list_resource_categories(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 100,
    status: str | None = None,
) -> ResourceCategoryPage:
    """分页查询物资分类。"""

    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    normalized_status = normalize_optional_text(status, field_label="分类状态", max_length=32)
    repository = MaterialRepository(session)
    items, total = await repository.list_categories(
        page=normalized_page,
        page_size=normalized_page_size,
        status=normalized_status,
    )
    return ResourceCategoryPage(items=items, page=normalized_page, page_size=normalized_page_size, total=total)


# --- 物资台账 ---
async def create_material(
    session: AsyncSession,
    *,
    name: str,
    total_quantity: int,
    available_quantity: int | None = None,
    category_id: int | None = None,
    description: str | None = None,
    location: str | None = None,
    cabinet_no: str | None = None,
    shelf_no: str | None = None,
    deposit_points: int = 0,
    status: str = MATERIAL_STATUS_AVAILABLE,
    operator_id: int | None = None,
) -> Material:
    """创建物资台账。"""

    repository = MaterialRepository(session)
    if category_id is not None:
        await _ensure_material_category_available(repository, category_id=category_id)

    normalized_total = normalize_non_negative_int(total_quantity, field_label="总数量")
    normalized_available = normalized_total if available_quantity is None else normalize_non_negative_int(
        available_quantity,
        field_label="可借数量",
    )
    ensure_available_not_greater_than_total(
        total_quantity=normalized_total,
        available_quantity=normalized_available,
    )
    normalized_status = _normalize_material_status(status)

    material = Material(
        category_id=category_id,
        name=normalize_required_text(name, field_label="物资名称", max_length=120),
        description=normalize_optional_text(description, field_label="物资说明", max_length=2000),
        location=normalize_optional_text(location, field_label="存放位置", max_length=120),
        cabinet_no=normalize_optional_text(cabinet_no, field_label="柜号", max_length=80),
        shelf_no=normalize_optional_text(shelf_no, field_label="层号", max_length=80),
        status=normalized_status,
        total_quantity=normalized_total,
        available_quantity=normalized_available,
        deposit_points=normalize_non_negative_int(deposit_points, field_label="单件押金积分"),
        created_by=operator_id,
        updated_by=operator_id,
    )
    return await repository.add_material(material)


async def get_material(session: AsyncSession, *, material_id: int) -> Material:
    """读取物资，不存在时抛出业务错误。"""

    repository = MaterialRepository(session)
    material = await repository.get_material_by_id(material_id)
    if material is None:
        raise AppError("MATERIAL_NOT_FOUND", "物资不存在", status_code=404)
    return material


async def list_materials(
    session: AsyncSession,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str | None = None,
    category_id: int | None = None,
    keyword: str | None = None,
) -> MaterialPage:
    """分页查询物资台账。"""

    normalized_page = max(page, 1)
    normalized_page_size = min(max(page_size, 1), 100)
    normalized_status = normalize_optional_text(status, field_label="物资状态", max_length=32)
    if normalized_status is not None:
        _normalize_material_status(normalized_status)
    normalized_keyword = normalize_optional_text(keyword, field_label="搜索关键词", max_length=80)

    repository = MaterialRepository(session)
    items, total = await repository.list_materials(
        page=normalized_page,
        page_size=normalized_page_size,
        status=normalized_status,
        category_id=category_id,
        keyword=normalized_keyword,
    )
    return MaterialPage(items=items, page=normalized_page, page_size=normalized_page_size, total=total)


async def update_material(
    session: AsyncSession,
    *,
    material_id: int,
    operator_id: int,
    name: str | None = None,
    category_id: int | None = None,
    description: str | None = None,
    location: str | None = None,
    cabinet_no: str | None = None,
    shelf_no: str | None = None,
    deposit_points: int | None = None,
    status: str | None = None,
) -> Material:
    """更新物资基础资料，不直接修改库存数量。"""

    repository = MaterialRepository(session)
    material = await repository.get_material_by_id(material_id, for_update=True)
    if material is None:
        raise AppError("MATERIAL_NOT_FOUND", "物资不存在", status_code=404)

    if category_id is not None:
        await _ensure_material_category_available(repository, category_id=category_id)
        material.category_id = category_id
    if name is not None:
        material.name = normalize_required_text(name, field_label="物资名称", max_length=120)
    if description is not None:
        material.description = normalize_optional_text(description, field_label="物资说明", max_length=2000)
    if location is not None:
        material.location = normalize_optional_text(location, field_label="存放位置", max_length=120)
    if cabinet_no is not None:
        material.cabinet_no = normalize_optional_text(cabinet_no, field_label="柜号", max_length=80)
    if shelf_no is not None:
        material.shelf_no = normalize_optional_text(shelf_no, field_label="层号", max_length=80)
    if deposit_points is not None:
        material.deposit_points = normalize_non_negative_int(deposit_points, field_label="单件押金积分")
    if status is not None:
        material.status = _normalize_material_status(status)

    material.updated_by = operator_id
    await session.flush()
    loaded_material = await repository.get_material_by_id(material.id)
    return loaded_material or material


async def adjust_material_stock(
    session: AsyncSession,
    *,
    material_id: int,
    total_quantity: int,
    available_quantity: int,
    operator_id: int,
) -> Material:
    """
    调整物资库存快照。

    该方法用于后台盘点、补货和异常修正。借用审批/归还不应该走这个入口，而应使用
    借用域的状态机，保证库存变化和申请状态在同一事务里完成。
    """

    normalized_total = normalize_non_negative_int(total_quantity, field_label="总数量")
    normalized_available = normalize_non_negative_int(available_quantity, field_label="可借数量")
    ensure_available_not_greater_than_total(
        total_quantity=normalized_total,
        available_quantity=normalized_available,
    )

    repository = MaterialRepository(session)
    material = await repository.get_material_by_id(material_id, for_update=True)
    if material is None:
        raise AppError("MATERIAL_NOT_FOUND", "物资不存在", status_code=404)

    material.total_quantity = normalized_total
    material.available_quantity = normalized_available
    material.updated_by = operator_id
    await session.flush()
    loaded_material = await repository.get_material_by_id(material.id)
    return loaded_material or material


# --- 内部校验 ---
async def _ensure_material_category_available(
    repository: MaterialRepository,
    *,
    category_id: int,
) -> ResourceCategory:
    """确认物资分类存在且可用。"""

    category = await repository.get_category_by_id(category_id)
    if category is None:
        raise AppError("RESOURCE_CATEGORY_NOT_FOUND", "资源分类不存在", status_code=404)
    if category.resource_type != RESOURCE_TYPE_MATERIAL:
        raise AppError("RESOURCE_CATEGORY_TYPE_INVALID", "资源分类不属于物资", status_code=422)
    if category.status != RESOURCE_CATEGORY_ACTIVE:
        raise AppError("RESOURCE_CATEGORY_DISABLED", "资源分类未启用", status_code=409)
    return category


def _normalize_material_status(status: str) -> str:
    """规范化物资状态。"""

    normalized_status = normalize_required_text(status, field_label="物资状态", max_length=32)
    if normalized_status not in MATERIAL_ACTIVE_STATUSES:
        raise AppError("MATERIAL_STATUS_INVALID", "物资状态不合法", status_code=422)
    return normalized_status
