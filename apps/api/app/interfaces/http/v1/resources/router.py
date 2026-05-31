# app/interfaces/http/v1/resources/router.py
"""
资源 V1 路由

第一阶段开放物资分类、物资台账和库存调整接口。借用申请不在这里处理，借用域通过
服务层在审批和归还时修改库存，保证资源台账和借用状态在同一事务内一致。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.core.security.middleware import get_client_ip
from app.interfaces.http.dependencies import CurrentUser, get_current_user, require_permission
from app.interfaces.http.v1.resources.schemas import (
    MaterialCreateRequest,
    MaterialPageResponse,
    MaterialResponse,
    MaterialStockUpdateRequest,
    MaterialUpdateRequest,
    ResourceCategoryCreateRequest,
    ResourceCategoryPageResponse,
    ResourceCategoryResponse,
)
from app.modules.audit.service import AuditLogEntry, record_audit_log
from app.modules.resources.materials import (
    adjust_material_stock,
    create_material,
    create_resource_category,
    get_material,
    list_materials,
    list_resource_categories,
    update_material,
)
from app.modules.resources.models import Material, ResourceCategory
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter()


# --- 响应转换 ---
def build_resource_category_response(category: ResourceCategory) -> ResourceCategoryResponse:
    """把资源分类 ORM 对象转换成接口响应。"""

    return ResourceCategoryResponse(
        id=category.id,
        name=category.name,
        resource_type=category.resource_type,
        status=category.status,
        sort_order=category.sort_order,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def build_material_response(material: Material) -> MaterialResponse:
    """把物资 ORM 对象转换成接口响应。"""

    return MaterialResponse(
        id=material.id,
        category_id=material.category_id,
        category_name=material.category.name if material.category is not None else None,
        name=material.name,
        description=material.description,
        location=material.location,
        cabinet_no=material.cabinet_no,
        shelf_no=material.shelf_no,
        status=material.status,
        total_quantity=material.total_quantity,
        available_quantity=material.available_quantity,
        deposit_points=material.deposit_points,
        created_by=material.created_by,
        updated_by=material.updated_by,
        created_at=material.created_at,
        updated_at=material.updated_at,
    )


def build_material_snapshot(material: Material) -> dict:
    """构造审计日志使用的物资快照。"""

    return build_material_response(material).model_dump(mode="json")


# --- 资源分类 ---
@router.get("/resources/material-categories")
async def get_material_categories(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    status: str | None = Query(default=None),
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查询物资分类。"""

    page_data = await list_resource_categories(
        session,
        page=page,
        page_size=page_size,
        status=status,
    )
    data = ResourceCategoryPageResponse(
        items=[build_resource_category_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/resources/material-categories")
async def create_material_category(
    payload: ResourceCategoryCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("resources.material.manage")),
    session: AsyncSession = Depends(get_session),
):
    """创建物资分类。"""

    category = await create_resource_category(
        session,
        name=payload.name,
        status=payload.status,
        sort_order=payload.sort_order,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="resources.material_category.create",
            target_type="resource_category",
            target_id=str(category.id),
            after_snapshot=build_resource_category_response(category).model_dump(mode="json"),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_resource_category_response(category)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


# --- 物资台账 ---
@router.get("/resources/materials")
async def get_materials(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: str | None = Query(default=None),
    category_id: int | None = Query(default=None),
    keyword: str | None = Query(default=None),
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """查询物资台账。"""

    page_data = await list_materials(
        session,
        page=page,
        page_size=page_size,
        status=status,
        category_id=category_id,
        keyword=keyword,
    )
    data = MaterialPageResponse(
        items=[build_material_response(item) for item in page_data.items],
        page=page_data.page,
        page_size=page_data.page_size,
        total=page_data.total,
    )
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.post("/resources/materials")
async def create_material_resource(
    payload: MaterialCreateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("resources.material.manage")),
    session: AsyncSession = Depends(get_session),
):
    """创建物资。"""

    material = await create_material(
        session,
        name=payload.name,
        category_id=payload.category_id,
        description=payload.description,
        location=payload.location,
        cabinet_no=payload.cabinet_no,
        shelf_no=payload.shelf_no,
        status=payload.status,
        total_quantity=payload.total_quantity,
        available_quantity=payload.available_quantity,
        deposit_points=payload.deposit_points,
        operator_id=current_user.user.id,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="resources.material.create",
            target_type="material",
            target_id=str(material.id),
            after_snapshot=build_material_snapshot(material),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_material_response(material)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.get("/resources/materials/{material_id}")
async def get_material_resource(
    material_id: int,
    request: Request,
    _: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """读取物资详情。"""

    material = await get_material(session, material_id=material_id)
    data = build_material_response(material)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.patch("/resources/materials/{material_id}")
async def update_material_resource(
    material_id: int,
    payload: MaterialUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("resources.material.manage")),
    session: AsyncSession = Depends(get_session),
):
    """更新物资基础资料。"""

    before = await get_material(session, material_id=material_id)
    before_snapshot = build_material_snapshot(before)
    material = await update_material(
        session,
        material_id=material_id,
        operator_id=current_user.user.id,
        name=payload.name,
        category_id=payload.category_id,
        description=payload.description,
        location=payload.location,
        cabinet_no=payload.cabinet_no,
        shelf_no=payload.shelf_no,
        status=payload.status,
        deposit_points=payload.deposit_points,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="resources.material.update",
            target_type="material",
            target_id=str(material.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_material_snapshot(material),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            risk_level="medium",
        ),
    )
    await session.commit()
    data = build_material_response(material)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))


@router.patch("/resources/materials/{material_id}/stock")
async def update_material_stock(
    material_id: int,
    payload: MaterialStockUpdateRequest,
    request: Request,
    current_user: CurrentUser = Depends(require_permission("resources.material.manage")),
    session: AsyncSession = Depends(get_session),
):
    """调整物资库存。"""

    before = await get_material(session, material_id=material_id)
    before_snapshot = build_material_snapshot(before)
    material = await adjust_material_stock(
        session,
        material_id=material_id,
        total_quantity=payload.total_quantity,
        available_quantity=payload.available_quantity,
        operator_id=current_user.user.id,
    )
    await record_audit_log(
        session,
        AuditLogEntry(
            actor_id=current_user.user.id,
            action="resources.material.stock_adjust",
            target_type="material",
            target_id=str(material.id),
            before_snapshot=before_snapshot,
            after_snapshot=build_material_snapshot(material),
            ip_address=get_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            request_id=get_request_id(request),
            reason=payload.reason,
            risk_level="high",
        ),
    )
    await session.commit()
    data = build_material_response(material)
    return success_response(data.model_dump(mode="json"), request_id=get_request_id(request))
