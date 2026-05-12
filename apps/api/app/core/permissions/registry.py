# app/core/permissions/registry.py
"""
权限点注册表

权限点是接口鉴权和后台菜单可见性的稳定契约。业务代码应该引用权限点 code，
不能直接比较身份数字。当前先建立内存注册表，后续数据库迁移会把这些权限点
同步为 `permissions` 表种子数据。
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class PermissionRiskLevel(StrEnum):
    """权限风险等级。"""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass(frozen=True)
class PermissionPoint:
    """
    权限点定义。

    code 必须稳定，进入数据库、前端菜单和审计日志后不能随意改名。
    """

    code: str
    name: str
    module: str
    description: str
    risk_level: PermissionRiskLevel = PermissionRiskLevel.LOW


class PermissionRegistry:
    """
    权限点内存注册表。

    注册表只负责“有哪些权限点”。用户是否拥有某个权限，需要后续授权关系、
    职务、部门和作用域规则共同判断。
    """

    def __init__(self) -> None:
        self._points: dict[str, PermissionPoint] = {}

    def register(self, point: PermissionPoint) -> None:
        """
        注册一个权限点。

        重复注册同一个 code 说明模块边界或命名出现冲突，应在启动阶段直接失败。
        """

        if point.code in self._points:
            raise ValueError(f"权限点重复注册: {point.code}")
        self._points[point.code] = point

    def get(self, code: str) -> PermissionPoint | None:
        """按 code 查询权限点。"""

        return self._points.get(code)

    def require(self, code: str) -> PermissionPoint:
        """按 code 查询权限点，不存在时抛出异常。"""

        point = self.get(code)
        if point is None:
            raise KeyError(f"权限点未注册: {code}")
        return point

    def list(self) -> list[PermissionPoint]:
        """列出全部已注册权限点。"""

        return sorted(self._points.values(), key=lambda item: item.code)


permission_registry = PermissionRegistry()


def register_core_permissions() -> None:
    """
    注册第一批核心权限点。

    当前只注册和已确认需求强相关的系统、组织和审计权限。业务域权限会跟随
    积分、资源、借用、项目等模块落地时再分批加入。
    """

    for point in [
        PermissionPoint(
            code="system.admin.access",
            name="访问后台管理端",
            module="system",
            description="允许进入后台管理端框架，具体菜单仍需业务权限控制。",
            risk_level=PermissionRiskLevel.MEDIUM,
        ),
        PermissionPoint(
            code="system.audit.view",
            name="查看审计日志",
            module="audit",
            description="查看系统审计日志和高风险操作记录。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="system.permission.manage",
            name="维护权限与角色",
            module="system",
            description="维护系统权限、角色和用户授权关系。",
            risk_level=PermissionRiskLevel.CRITICAL,
        ),
        PermissionPoint(
            code="system.operator.manage",
            name="指定或移除管理员",
            module="system",
            description="由唯一 999 指定或移除 998 管理员。",
            risk_level=PermissionRiskLevel.CRITICAL,
        ),
        PermissionPoint(
            code="organization.member.manage",
            name="维护成员资料",
            module="organization",
            description="维护他人成员资料，不包含系统登录凭证和积分余额。",
            risk_level=PermissionRiskLevel.MEDIUM,
        ),
        PermissionPoint(
            code="organization.department.manage",
            name="维护部门归属",
            module="organization",
            description="调整成员部门关系和部门基础信息。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="organization.position.manage",
            name="维护职务身份",
            module="organization",
            description="授予或撤销部长、副会长、会长、指导老师等职务身份。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="system.super_admin.recover",
            name="灾备恢复超级管理员",
            module="system",
            description="受控恢复唯一 999 超级管理员，只能由运维脚本或灾备流程触发。",
            risk_level=PermissionRiskLevel.CRITICAL,
        ),
        PermissionPoint(
            code="files.upload",
            name="上传文件",
            module="files",
            description="允许通过统一文件接口上传业务文件。",
            risk_level=PermissionRiskLevel.MEDIUM,
        ),
        PermissionPoint(
            code="files.manage",
            name="维护文件元数据",
            module="files",
            description="维护文件元数据、状态和存储对象引用。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="points.ledger.view",
            name="查看积分账本",
            module="points",
            description="查看成员积分账户和积分流水。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="points.rule.view",
            name="查看积分规则",
            module="points",
            description="查看固定积分规则、临时规则申请和一次性任务模板。",
            risk_level=PermissionRiskLevel.MEDIUM,
        ),
        PermissionPoint(
            code="points.rule.manage",
            name="维护固定积分规则",
            module="points",
            description="创建或撤回固定积分规则，不包含系统兜底人工改分。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="points.temporary_rule.apply",
            name="提交临时积分规则",
            module="points",
            description="为特殊非模板任务提交临时积分规则申请。",
            risk_level=PermissionRiskLevel.MEDIUM,
        ),
        PermissionPoint(
            code="points.temporary_rule.review",
            name="审批临时积分规则",
            module="points",
            description="审批、驳回或撤回临时积分规则，并生成一次性任务模板。",
            risk_level=PermissionRiskLevel.HIGH,
        ),
        PermissionPoint(
            code="points.manual.adjust",
            name="人工调整积分",
            module="points",
            description="受控人工补发或扣减积分，用于系统兜底和异常修复。",
            risk_level=PermissionRiskLevel.CRITICAL,
        ),
    ]:
        if permission_registry.get(point.code) is None:
            permission_registry.register(point)


register_core_permissions()
