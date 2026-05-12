# app/modules/workbench/tasks/repository.py
"""
工作台任务仓储

本文件只封装 workbench_tasks 的查询与写入。任务状态机、领取范围、审核发分和跨域规则
放在 service.py，仓储层不提交事务。
"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.workbench.constants import WORKBENCH_TASK_STATUS_PENDING_CLAIM
from app.modules.workbench.models import WorkbenchTask


class WorkbenchTaskRepository:
    """工作台任务仓储。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_task_by_id(self, task_id: int, *, for_update: bool = False) -> WorkbenchTask | None:
        """按 ID 查询任务。"""

        statement = (
            select(WorkbenchTask)
            .options(
                selectinload(WorkbenchTask.point_rule),
                selectinload(WorkbenchTask.point_ledger_entry),
            )
            .where(WorkbenchTask.id == task_id)
        )
        if for_update:
            statement = statement.with_for_update()
        return await self.session.scalar(statement)

    async def add_task(self, task: WorkbenchTask) -> WorkbenchTask:
        """写入任务，并返回已经带出积分规则关系的任务快照。"""

        self.session.add(task)
        await self.session.flush()
        loaded_task = await self.get_task_by_id(task.id)
        return loaded_task or task

    async def list_tasks(
        self,
        *,
        page: int,
        page_size: int,
        viewer_id: int | None = None,
        status: str | None = None,
        mine: bool = False,
        available_to_claim: bool = False,
    ) -> tuple[list[WorkbenchTask], int]:
        """分页查询任务。"""

        conditions = []
        if status is not None:
            conditions.append(WorkbenchTask.status == status)
        if mine and viewer_id is not None:
            conditions.append(
                or_(
                    WorkbenchTask.publisher_id == viewer_id,
                    WorkbenchTask.assignee_id == viewer_id,
                ),
            )
        if available_to_claim:
            conditions.append(WorkbenchTask.status == WORKBENCH_TASK_STATUS_PENDING_CLAIM)

        statement = (
            select(WorkbenchTask)
            .options(
                selectinload(WorkbenchTask.point_rule),
                selectinload(WorkbenchTask.point_ledger_entry),
            )
            .where(*conditions)
            .order_by(WorkbenchTask.created_at.desc(), WorkbenchTask.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        count_statement = select(func.count(WorkbenchTask.id)).where(*conditions)
        result = await self.session.scalars(statement)
        total = await self.session.scalar(count_statement)
        return list(result), total or 0
