# 积分 HTTP 接口

本目录负责积分账本的 V1 HTTP 契约，包括当前用户查询、后台查询、受控人工调整、
反向流水修正、固定规则维护和临时规则审批。

## 当前接口

- `GET /api/v1/me/points/account`：当前用户查看自己的积分账户；
- `GET /api/v1/me/points/ledger`：当前用户查看自己的积分流水；
- `GET /api/v1/points/accounts/{user_id}`：后台查看指定用户积分账户，需要 `points.ledger.view`；
- `GET /api/v1/points/ledger`：后台查询积分流水，需要 `points.ledger.view`；
- `POST /api/v1/points/ledger/{ledger_entry_id}/reverse`：后台反向修正流水，需要 `points.manual.adjust`；
- `GET /api/v1/points/rules`：后台查看积分规则，需要 `points.rule.view`；
- `POST /api/v1/points/rules`：后台创建固定积分规则，需要 `points.rule.manage`；
- `POST /api/v1/points/rules/{rule_id}/revoke`：后台撤回积分规则，需要 `points.rule.manage`；
- `GET /api/v1/points/rules/temporary`：后台查看临时规则申请，需要 `points.rule.view`；
- `POST /api/v1/points/rules/temporary`：提交临时积分规则申请，需要 `points.temporary_rule.apply`；
- `POST /api/v1/points/rules/temporary/{rule_id}/approve`：审批临时规则，需要 `points.temporary_rule.review`；
- `POST /api/v1/points/rules/temporary/{rule_id}/reject`：驳回临时规则，需要 `points.temporary_rule.review`；
- `POST /api/v1/points/rules/temporary/{rule_id}/revoke`：撤回临时规则，需要 `points.temporary_rule.review`；
- `POST /api/v1/points/manual-adjustments`：后台受控人工调整积分，需要 `points.manual.adjust`。

## 契约约束

- 成功响应使用统一 `success/data/message/request_id` 结构，不返回旧式顶层 `code: 200`；
- 人工调整必须提供 `Idempotency-Key` 请求头或请求体 `idempotency_key`；
- 反向流水修正必须提供 `Idempotency-Key` 请求头或请求体 `idempotency_key`；
- 人工调整必须填写原因，并写入 `points.manual_adjustment.create` 审计；
- 固定规则创建和撤回写入 `points.rule.create` / `points.rule.revoke` 审计；
- 临时规则提交、审批、驳回和撤回写入 `points.temporary_rule.*` 审计；
- 临时规则撤回默认停止后续使用，不自动追回已发积分；
- 当前目录不开放冻结、解冻和冻结转扣除的外部接口，这些能力先由业务域服务层调用；
- `998/999` 不默认拥有积分规则审批权限，只通过 `points.manual.adjust` 做系统兜底。
