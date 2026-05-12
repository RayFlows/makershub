# app/modules/points/rules/__init__.py
"""
积分规则能力导出

积分规则包含固定规则、临时规则申请审批，以及审批通过后生成的一次性任务模板。
外部业务域需要发放规则积分时，应调用这里暴露的服务函数，不能直接写积分流水。
"""

from app.modules.points.rules.service import (
    approve_temporary_point_rule,
    create_point_rule,
    grant_points_by_rule,
    list_point_rules,
    list_temporary_point_rules,
    reject_temporary_point_rule,
    revoke_point_rule,
    revoke_temporary_point_rule,
    submit_temporary_point_rule,
)

__all__ = [
    "approve_temporary_point_rule",
    "create_point_rule",
    "grant_points_by_rule",
    "list_point_rules",
    "list_temporary_point_rules",
    "reject_temporary_point_rule",
    "revoke_point_rule",
    "revoke_temporary_point_rule",
    "submit_temporary_point_rule",
]
