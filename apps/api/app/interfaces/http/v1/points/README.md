# 积分 HTTP 接口

本目录负责积分账本的 V1 HTTP 契约，包括当前用户查询、后台查询和受控人工调整。

## 当前接口

- `GET /api/v1/me/points/account`：当前用户查看自己的积分账户；
- `GET /api/v1/me/points/ledger`：当前用户查看自己的积分流水；
- `GET /api/v1/points/accounts/{user_id}`：后台查看指定用户积分账户，需要 `points.ledger.view`；
- `GET /api/v1/points/ledger`：后台查询积分流水，需要 `points.ledger.view`；
- `POST /api/v1/points/manual-adjustments`：后台受控人工调整积分，需要 `points.manual.adjust`。

## 契约约束

- 成功响应使用统一 `success/data/message/request_id` 结构，不返回旧式顶层 `code: 200`；
- 人工调整必须提供 `Idempotency-Key` 请求头或请求体 `idempotency_key`；
- 人工调整必须填写原因，并写入 `points.manual_adjustment.create` 审计；
- 当前目录不开放冻结、解冻和冻结转扣除的外部接口，这些能力先由业务域服务层调用；
- 临时积分规则和固定积分规则接口后续单独补充。
