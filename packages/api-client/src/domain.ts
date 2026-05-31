export interface StatusMeta {
  label: string;
  color: string;
}

export const workbenchTaskStatusMeta: Record<string, StatusMeta> = {
  pending_claim: { label: "待领取", color: "cyan" },
  pending_completion: { label: "待完成", color: "gold" },
  pending_review: { label: "待审核", color: "orange" },
  completed: { label: "已完成", color: "green" },
  rejected: { label: "已打回", color: "red" },
  cancelled: { label: "已取消", color: "default" },
  rule_revoked_pending: { label: "规则待处理", color: "volcano" },
};

export const visibilityLabels: Record<string, string> = {
  association: "协会内",
  department: "部门内",
  public: "公开",
};

export function getWorkbenchTaskStatusMeta(status: string): StatusMeta {
  return workbenchTaskStatusMeta[status] || { label: status, color: "default" };
}
