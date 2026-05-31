# app/modules/resources/materials/repository.py
"""
物资资源仓储

仓储层只封装资源分类和物资表的查询写入，不提交事务，也不判断借用审批规则。
库存能否扣减、是否需要审计，由服务层和调用方负责。
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.resources.constants import RESOURCE_TYPE_MATERIAL
from app.modules.resources.models import Material, ResourceCategory


class MaterialRepository:
    """物资资源仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_category(self, category: ResourceCategory) -> ResourceCategory:
        """写入资源分类。"""

        self.session.add(category)
        await self.session.flush()
        await self.session.refresh(category)
        return category

    async def get_category_by_id(self, category_id: int) -> ResourceCategory | None:
        """按 ID 读取资源分类。"""

        return await self.session.scalar(
            select(ResourceCategory).where(ResourceCategory.id == category_id),
        )

    async def list_categories(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
    ) -> tuple[list[ResourceCategory], int]:
        """分页查询物资分类。"""

        conditions = [ResourceCategory.resource_type == RESOURCE_TYPE_MATERIAL]
        if status is not None:
            conditions.append(ResourceCategory.status == status)
        statement = (
            select(ResourceCategory)
            .where(*conditions)
            .order_by(ResourceCategory.sort_order.asc(), ResourceCategory.id.asc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(ResourceCategory.id)).where(*conditions)
        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)
        return list(result), total or 0

    async def add_material(self, material: Material) -> Material:
        """写入物资。"""

        self.session.add(material)
        await self.session.flush()
        loaded_material = await self.get_material_by_id(material.id)
        return loaded_material or material

    async def get_material_by_id(self, material_id: int, *, for_update: bool = False) -> Material | None:
        """按 ID 读取物资。"""

        statement = (
            select(Material)
            .options(selectinload(Material.category))
            .where(Material.id == material_id)
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list_materials(
        self,
        *,
        page: int,
        page_size: int,
        status: str | None = None,
        category_id: int | None = None,
        keyword: str | None = None,
    ) -> tuple[list[Material], int]:
        """分页查询物资。"""

        conditions = []
        if status is not None:
            conditions.append(Material.status == status)
        if category_id is not None:
            conditions.append(Material.category_id == category_id)
        if keyword is not None:
            like_keyword = f"%{keyword}%"
            conditions.append(
                or_(
                    Material.name.like(like_keyword),
                    Material.description.like(like_keyword),
                    Material.location.like(like_keyword),
                ),
            )

        statement = (
            select(Material)
            .options(selectinload(Material.category))
            .where(*conditions)
            .order_by(Material.updated_at.desc(), Material.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(Material.id)).where(*conditions)
        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)
        return list(result), total or 0
