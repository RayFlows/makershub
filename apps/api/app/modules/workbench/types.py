# app/modules/workbench/types.py
"""
工作台服务层结果对象

任务列表和任务状态流转会被小程序、成员网页端和后台管理端复用。服务层使用明确结果
对象，避免接口层自己拼分页结构或猜测任务是否已经产生积分流水。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.workbench.models import WorkbenchTask


@dataclass(frozen=True)
class WorkbenchTaskPage:
    """工作台任务分页结果。"""

    items: list[WorkbenchTask]
    page: int
    page_size: int
    total: int
