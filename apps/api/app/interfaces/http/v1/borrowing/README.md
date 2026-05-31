# 借用 V1 接口

负责暴露借用申请、修改、审批、取消和归还 HTTP 契约。

## 已落地接口

- `POST /api/v1/borrowing/applications`
- `PATCH /api/v1/borrowing/applications/{application_id}`
- `GET /api/v1/borrowing/applications`
- `GET /api/v1/borrowing/applications/{application_id}`
- `POST /api/v1/borrowing/applications/{application_id}/cancel`
- `POST /api/v1/borrowing/applications/{application_id}/review`
- `POST /api/v1/borrowing/applications/{application_id}/return`

第一阶段 `borrow_type` 仅支持 `material`。普通成员只能查看、修改和取消自己的申请；
拥有 `borrowing.application.review` 权限的用户可以查看全部申请、审核和确认归还。

修改申请当前状态是“HTTP 已开放”，不是“端侧已接入”。请求体必须完整提交
`reason`、`expected_return_at` 和整份 `items`，额外字段会被拒绝；只允许申请人本人
修改 `pending_review` 或 `rejected` 申请，修改已驳回申请后回到 `pending_review` 并
保留原审核记录，成功后刷新 `submitted_at`。
