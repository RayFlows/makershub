# app/modules/borrowing/materials/repository.py
"""
物资借用仓储

仓储层负责借用申请、明细、审核和归还记录的查询写入。状态流转、库存扣减和积分冻结
必须放在 service.py，避免数据库访问层掺入跨域业务规则。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.borrowing.constants import BORROW_TYPE_MATERIAL
from app.modules.borrowing.models import BorrowApplication, BorrowItem, BorrowReturn, BorrowReview


class MaterialBorrowRepository:
    """物资借用仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add_application(self, application: BorrowApplication) -> BorrowApplication:
        """写入借用申请。"""

        self.session.add(application)
        await self.session.flush()
        loaded_application = await self.get_application_by_id(application.id)
        return loaded_application or application

    async def get_application_by_id(
        self,
        application_id: int,
        *,
        for_update: bool = False,
    ) -> BorrowApplication | None:
        """按 ID 读取申请快照。"""

        statement = (
            select(BorrowApplication)
            .options(
                selectinload(BorrowApplication.items).selectinload(BorrowItem.material),
                selectinload(BorrowApplication.reviews),
                selectinload(BorrowApplication.returns),
                selectinload(BorrowApplication.point_hold),
            )
            .where(BorrowApplication.id == application_id)
            .execution_options(populate_existing=True)
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def list_applications(
        self,
        *,
        page: int,
        page_size: int,
        applicant_id: int | None = None,
        status: str | None = None,
    ) -> tuple[list[BorrowApplication], int]:
        """分页查询借用申请。"""

        conditions = [BorrowApplication.borrow_type == BORROW_TYPE_MATERIAL]
        if applicant_id is not None:
            conditions.append(BorrowApplication.applicant_id == applicant_id)
        if status is not None:
            conditions.append(BorrowApplication.status == status)

        statement = (
            select(BorrowApplication)
            .options(
                selectinload(BorrowApplication.items).selectinload(BorrowItem.material),
                selectinload(BorrowApplication.reviews),
                selectinload(BorrowApplication.returns),
                selectinload(BorrowApplication.point_hold),
            )
            .where(*conditions)
            .execution_options(populate_existing=True)
            .order_by(BorrowApplication.submitted_at.desc(), BorrowApplication.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(BorrowApplication.id)).where(*conditions)
        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)
        return list(result), total or 0

    async def add_review(self, review: BorrowReview) -> BorrowReview:
        """写入审核记录。"""

        self.session.add(review)
        await self.session.flush()
        await self.session.refresh(review)
        return review

    async def add_return(self, borrow_return: BorrowReturn) -> BorrowReturn:
        """写入归还记录。"""

        self.session.add(borrow_return)
        await self.session.flush()
        await self.session.refresh(borrow_return)
        return borrow_return
