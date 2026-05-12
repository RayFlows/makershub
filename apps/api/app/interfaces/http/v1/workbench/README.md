# 工作台 HTTP 接口

本目录负责工作台 V1 HTTP 契约。当前先开放任务闭环，排班和值班接口仍按文档规划后续补齐。

## 当前接口

- `POST /api/v1/workbench/tasks`：发布任务，需要 `workbench.task.publish`；
- `GET /api/v1/workbench/tasks`：查询任务，需要登录；
- `POST /api/v1/workbench/tasks/{task_id}/claim`：领取悬赏任务，需要登录；
- `POST /api/v1/workbench/tasks/{task_id}/submit`：执行人提交完成材料，需要登录；
- `POST /api/v1/workbench/tasks/{task_id}/review`：发布人审核任务，需要登录且必须是发布人。

## 契约约束

- 成功响应使用统一 `success/data/message/request_id` 结构；
- 任务发布必须引用已有积分规则，不能临时填写积分数；
- 指定任务发布后直接 `pending_completion`；
- 悬赏任务发布后 `pending_claim`，领取后进入 `pending_completion`；
- 执行人提交完成材料后进入 `pending_review`；
- 审核通过后按积分规则发放积分，并把积分流水 ID 写回任务；
- 如果审核时积分规则已撤回，任务进入 `rule_revoked_pending`，不自动发分。
