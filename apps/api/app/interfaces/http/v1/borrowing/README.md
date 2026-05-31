# 借用 V1 接口

负责暴露借用申请、审批、取消和归还 HTTP 契约。

## 已落地接口

- `POST /api/v1/borrowing/applications`
- `GET /api/v1/borrowing/applications`
- `GET /api/v1/borrowing/applications/{application_id}`
- `POST /api/v1/borrowing/applications/{application_id}/cancel`
- `POST /api/v1/borrowing/applications/{application_id}/review`
- `POST /api/v1/borrowing/applications/{application_id}/return`

第一阶段 `borrow_type` 仅支持 `material`。普通成员只能查看和取消自己的申请；
拥有 `borrowing.application.review` 权限的用户可以查看全部申请、审核和确认归还。
