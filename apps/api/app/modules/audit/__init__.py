# app/modules/audit/__init__.py
"""
审计领域导出

审计模块负责重要操作记录，不负责实际业务修改。业务服务在完成状态变更时调用
审计服务，把操作人、目标对象和前后快照写入 append-only 审计表。
"""

from app.modules.audit.models import AuditLog
from app.modules.audit.service import AuditLogEntry, record_audit_log

__all__ = ["AuditLog", "AuditLogEntry", "record_audit_log"]

