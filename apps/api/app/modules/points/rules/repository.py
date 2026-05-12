# app/modules/points/rules/repository.py
"""
积分规则仓储

本文件封装 point_rules、temporary_point_rules 和 temporary_point_rule_events 的
查询与写入。审批能不能通过、撤回能不能执行等业务规则放在 service.py，仓储层只
负责数据库访问，不提交事务。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.points.models import PointRule, TemporaryPointRule, TemporaryPointRuleEvent


class PointRuleRepository:
    """积分规则仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # --- 固定规则和一次性模板 ---
    async def get_point_rule_by_id(self, rule_id: int) -> PointRule | None:
        """按 ID 查询积分规则。"""

        statement = select(PointRule).where(PointRule.id == rule_id)
        return await self.session.scalar(statement)

    async def get_point_rule_by_code(self, code: str) -> PointRule | None:
        """按稳定 code 查询积分规则。"""

        statement = select(PointRule).where(PointRule.code == code)
        return await self.session.scalar(statement)

    async def add_point_rule(self, rule: PointRule) -> PointRule:
        """写入积分规则。"""

        self.session.add(rule)
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def list_point_rules(
        self,
        *,
        include_revoked: bool = False,
        rule_type: str | None = None,
    ) -> list[PointRule]:
        """列出积分规则。"""

        conditions = []
        if not include_revoked:
            conditions.append(PointRule.status != "revoked")
        if rule_type is not None:
            conditions.append(PointRule.rule_type == rule_type)

        statement = (
            select(PointRule)
            .where(*conditions)
            .order_by(PointRule.rule_type, PointRule.status, PointRule.code)
        )
        result = await self.session.scalars(statement)
        return list(result)

    # --- 临时规则申请 ---
    async def get_temporary_rule_by_id(self, rule_id: int) -> TemporaryPointRule | None:
        """按 ID 查询临时积分规则申请。"""

        statement = (
            select(TemporaryPointRule)
            .options(selectinload(TemporaryPointRule.generated_point_rule))
            .where(TemporaryPointRule.id == rule_id)
        )
        return await self.session.scalar(statement)

    async def add_temporary_rule(self, rule: TemporaryPointRule) -> TemporaryPointRule:
        """写入临时积分规则申请。"""

        self.session.add(rule)
        await self.session.flush()
        await self.session.refresh(rule)
        return rule

    async def list_temporary_rules(
        self,
        *,
        page: int,
        page_size: int,
        approval_status: str | None = None,
    ) -> tuple[list[TemporaryPointRule], int]:
        """分页列出临时积分规则申请。"""

        conditions = []
        if approval_status is not None:
            conditions.append(TemporaryPointRule.approval_status == approval_status)

        statement = (
            select(TemporaryPointRule)
            .options(selectinload(TemporaryPointRule.generated_point_rule))
            .where(*conditions)
            .order_by(TemporaryPointRule.created_at.desc(), TemporaryPointRule.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(TemporaryPointRule.id)).where(*conditions)
        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)
        return list(result), total or 0

    # --- 临时规则事件 ---
    async def add_temporary_rule_event(self, event: TemporaryPointRuleEvent) -> TemporaryPointRuleEvent:
        """写入临时积分规则生命周期事件。"""

        self.session.add(event)
        await self.session.flush()
        return event
