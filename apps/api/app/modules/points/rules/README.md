# 积分规则能力

本目录负责积分域里的固定规则、临时规则申请审批、一次性任务模板和按规则发放积分。

## 负责什么

- 创建和撤回固定积分规则；
- 提交临时积分规则申请；
- 审批、驳回和撤回临时积分规则；
- 临时规则审批通过后生成一次性任务模板；
- 给后续任务、值班、打扫卫生等业务域提供 `grant_points_by_rule(...)` 内部发放入口。

## 不负责什么

- 不负责任务发布、任务领取和任务审核；
- 不负责通知触达，只保存 `revoke_impact_note` 作为后续通知和任务处理依据；
- 不负责 998/999 系统兜底人工改分，人工调整仍在 `points.adjustments`；
- 不负责删除已产生流水，异常追回必须走 `points.ledger.reverse_ledger_entry(...)`。

## 状态约束

- 固定规则由 `points.rule.manage` 创建或撤回；
- 临时规则申请由 `points.temporary_rule.apply` 提交；
- 临时规则审批、驳回和撤回由 `points.temporary_rule.review` 处理；
- `998/999` 不默认拥有积分规则审批权限，只保留 `points.manual.adjust` 兜底能力；
- 临时规则撤回默认只停止后续使用，不自动追回已发积分；
- 只有规则错误、重复发放、恶意滥用或审批失误等异常场景，才允许追加反向流水。

## 调用链路

```text
POST /api/v1/points/rules/temporary
  -> submit_temporary_point_rule
  -> temporary_point_rules + temporary_point_rule_events

POST /api/v1/points/rules/temporary/{id}/approve
  -> approve_temporary_point_rule
  -> point_rules(temporary_task_template) + temporary_point_rule_events

workbench 后续任务审核通过
  -> grant_points_by_rule
  -> point_accounts + point_ledger_entries

异常追回
  -> points.ledger.reverse_ledger_entry
  -> point_accounts + point_ledger_entries(ledger_reversal)
```
