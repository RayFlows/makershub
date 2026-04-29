# MakersHub 数据库设计草案

## 目标

本文档记录第一阶段数据库设计草案。当前只定义核心表、关系和约束方向，具体字段长度、索引名称和迁移脚本在实现前继续细化。

数据库采用 MySQL。后端通过 SQLAlchemy 和 Alembic 管理模型与迁移。

## 通用约定

所有核心业务表默认包含：

- `id`：内部主键；
- `created_at`：创建时间；
- `updated_at`：更新时间；
- `deleted_at`：软删除时间，可选；
- `created_by`：创建人，可选；
- `updated_by`：最后修改人，可选；
- `remark`：备注，可选。

重要业务记录不直接物理删除。涉及积分、权限、审批、封禁、撤回、损耗和审计的记录必须保留历史。

## 身份与登录

### `users`

用户主体表，表示系统中的一个人。

核心字段：

- `id`；
- `display_name`；
- `avatar_url`；
- `status`：正常、限制、封禁；
- `last_login_at`。

说明：

- 用户主体不直接等于微信 `openid` 或邮箱。
- 微信身份、本地账号密码都挂接到同一个用户主体。
- 普通用户第一版由小程序微信登录创建或找到用户主体，再通过绑定邮箱补齐本地账号入口。
- 第一个 `999` 是例外，可以由受控运维初始化命令先创建本地账号对应的用户主体。

### `local_accounts`

本地账号表，用于网页端、后台管理端和第一个 `999` 初始化。

核心字段：

- `id`；
- `user_id`；
- `email`；
- `password_hash`，可空，邮箱已绑定但首次设置密码前为空；
- `password_set_at`，可空；
- `email_verified_at`；
- `status`。

约束：

- `email` 全局唯一。
- 普通用户的 `local_accounts` 应由已绑定邮箱的用户主体生成，不作为网页端自助注册入口。
- 网页端首次邮箱验证码登录只消费已绑定到用户主体的邮箱，验证后强制设置密码。
- `password_hash` 为空时不能进行邮箱密码登录，只能走首次登录设置密码流程。
- 第一个 `999` 初始化可以直接创建本地账号，后续再绑定微信身份。
- 更换邮箱需要验证旧邮箱和新邮箱，密码保持不变。

### `wechat_accounts`

微信身份表，用于小程序登录。

核心字段：

- `id`；
- `user_id`；
- `openid`；
- `unionid`，可空；
- `session_key_hash`，可选；
- `bound_at`；
- `status`。

约束：

- `openid` 全局唯一。
- 第一版普通用户以微信身份作为进入系统的前置身份，不依赖 `unionid` 才能启动。
- 第一版不允许用户自助解绑微信。

### `email_verification_codes`

邮箱验证码记录表。

核心字段：

- `id`；
- `email`；
- `purpose`：绑定、首次登录、重置密码、更换邮箱；
- `code_hash`；
- `expires_at`；
- `consumed_at`；
- `request_ip`；
- `user_id`，可空。

规则：

- 验证码有效期 5 分钟。
- 同一邮箱 1 小时最多发送 10 次。
- 每次重新请求至少间隔 1 分钟。
- `bind_email` 类验证码由已登录小程序用户发起，用于把邮箱绑定到当前用户主体。
- `first_login` 类验证码用于网页端首次登录，只允许命中已绑定邮箱的用户主体，不创建普通新用户。

当前实现状态：

- 已创建 `users`、`local_accounts`、`wechat_accounts`、`email_verification_codes`；
- 已允许 `local_accounts.password_hash` 在首次设置密码前为空；
- 已创建密码哈希工具；
- 已创建初始化唯一 `999` 的服务；
- 已创建微信用户主体和待设置密码本地账号的服务层逻辑；
- 已创建微信登录接口、访问令牌签发和当前用户校验接口；
- 验证码发送、首次设置密码和邮箱密码登录仍待实现。

## 组织与成员

### `departments`

部门表。

初始部门：

- 宣传部；
- 基管部；
- 项目部；
- 运维部。

核心字段：

- `id`；
- `code`；
- `name`；
- `status`；
- `sort_order`。

### `member_profiles`

成员资料表。

核心字段：

- `id`；
- `user_id`；
- `real_name`；
- `student_id`；
- `phone`；
- `email`；
- `college`；
- `major`；
- `grade`；
- `qq`；
- `bio`。

说明：

- 申请表中能从成员资料带出的字段，不应重复手填。

### `department_memberships`

部门成员关系表。

核心字段：

- `id`；
- `user_id`；
- `department_id`；
- `status`；
- `joined_at`；
- `left_at`。

### `positions`

职务定义表。

初始职务：

- 干事；
- 部长；
- 副会长；
- 会长；
- 指导老师；
- 管理员 `998`；
- 超级管理员 `999`。

### `user_positions`

用户职务关系表。

核心字段：

- `id`；
- `user_id`；
- `position_id`；
- `department_id`，可空；
- `scope_type`；
- `scope_id`；
- `granted_by`；
- `granted_at`；
- `revoked_at`。

说明：

- `998/999` 是绑定到用户上的附加系统管理身份，不是独立后台账号。
- 全系统只能有一个有效 `999`。

当前实现状态：

- 已创建 `positions` 和 `user_positions`；
- 首批迁移会初始化干事、部长、副会长、会长、指导老师、`998` 和 `999`；
- 部门、成员资料和部门成员关系仍待实现。

## 权限

### `permissions`

权限点表。

核心字段：

- `id`；
- `code`；
- `name`；
- `description`；
- `module`；
- `risk_level`。

说明：

- 接口鉴权检查权限点，不直接使用 `identity_code >= 1` 这类数字比较。

### `roles`

角色表。

核心字段：

- `id`；
- `code`；
- `name`；
- `description`；
- `is_system`。

### `role_permissions`

角色权限关系表。

核心字段：

- `role_id`；
- `permission_id`。

### `user_roles`

用户角色关系表。

核心字段：

- `id`；
- `user_id`；
- `role_id`；
- `scope_type`；
- `scope_id`；
- `granted_by`；
- `granted_at`；
- `revoked_at`。

说明：

- 作用域可以是全局、部门、项目、场地等。

## 积分与账本

### `point_accounts`

积分账户表。

核心字段：

- `id`；
- `user_id`；
- `balance`；
- `frozen_balance`；
- `status`。

约束：

- 每个用户一个积分账户。
- 不允许透支。

### `point_ledger_entries`

积分流水表。

核心字段：

- `id`；
- `account_id`；
- `user_id`；
- `direction`：收入、支出、冻结、解冻、冻结转扣除、反向修正；
- `amount`；
- `available_balance_after`；
- `frozen_balance_after`；
- `business_type`；
- `business_id`；
- `idempotency_key`；
- `reason`；
- `operator_id`，可空。

约束：

- `idempotency_key` 唯一，防止同一业务事件重复发放积分。
- 流水不删除，撤回通过反向流水修正。

### `point_holds`

积分冻结表。

核心字段：

- `id`；
- `account_id`；
- `amount`；
- `business_type`；
- `business_id`；
- `status`：冻结中、已解冻、已扣除；
- `created_by`；
- `released_at`；
- `deducted_at`。

### `point_rules`

固定积分规则表。

核心字段：

- `id`；
- `code`；
- `name`；
- `amount`；
- `rule_type`；
- `status`；
- `version`；
- `effective_from`；
- `effective_to`。

### `temporary_point_rules`

临时积分规则表。

核心字段：

- `id`；
- `name`；
- `task_type`；
- `department_id`，可空；
- `reason`；
- `amount_per_completion`；
- `max_participants`；
- `total_points_limit`；
- `effective_from`；
- `effective_to`；
- `approval_status`；
- `applicant_id`；
- `approved_by`；
- `approved_at`；
- `revoke_status`；
- `revoked_by`；
- `revoked_at`；
- `revoke_reason`；
- `revoke_impact_note`。

规则：

- 特殊非模板任务不能直接发布，必须先申请临时积分规则。
- 临时积分规则审批通过后生成一次性任务模板。
- 撤回默认停止后续使用，不自动追回已发积分。
- 只有规则错误、重复发放、恶意滥用或审批失误等异常场景，才通过反向流水追回积分。

## 资源

### `resource_categories`

资源分类表。

核心字段：

- `id`；
- `name`；
- `type`：物资、场地、工位、设备；
- `status`；
- `sort_order`。

### `materials`

物资表。

核心字段：

- `id`；
- `category_id`；
- `name`；
- `description`；
- `location`；
- `cabinet_no`；
- `shelf_no`；
- `total_quantity`；
- `available_quantity`；
- `status`：可用、维修中、停用、下架。

### `sites`

场地表。

核心字段：

- `id`；
- `name`；
- `description`；
- `location`；
- `status`。

### `workstations`

工位表。

核心字段：

- `id`；
- `site_id`；
- `name`；
- `type`：流动工位、流动固定工位、管理工位、项目工位；
- `allow_personal_items`；
- `point_rule_type`；
- `status`。

## 借用

### `borrow_applications`

借用申请表。

核心字段：

- `id`；
- `applicant_id`；
- `borrow_type`：物资、场地、工位；
- `usage_type`：个人、项目；
- `project_id`，可空；
- `reason`；
- `expected_return_at`；
- `status`：草稿、待审核、已打回、已通过、已取消、待归还、已归还、异常关闭；
- `point_hold_id`，可空；
- `submitted_at`；
- `cancelled_at`；
- `cancel_reason`。

### `borrow_items`

借用明细表。

核心字段：

- `id`；
- `application_id`；
- `resource_type`；
- `resource_id`；
- `quantity`；
- `site_id`，可空；
- `workstation_id`，可空。

### `borrow_reviews`

借用审核记录表。

核心字段：

- `id`；
- `application_id`；
- `reviewer_id`；
- `decision`：通过、打回；
- `comment`；
- `reviewed_at`。

### `borrow_returns`

归还记录表。

核心字段：

- `id`；
- `application_id`；
- `operator_id`；
- `returned_at`；
- `condition`：正常、损坏、丢失、已损耗；
- `comment`；
- `point_action`。

## 项目

### `projects`

项目表。

核心字段：

- `id`；
- `project_no`；
- `name`；
- `type`：个人项目、比赛项目；
- `description`；
- `leader_id`；
- `mentor_name`；
- `mentor_phone`；
- `start_at`；
- `end_at`；
- `status`：草稿、待审核、进行中、已打回、待结项审核、已结项、中断、限制、封禁；
- `is_recruiting`；
- `open_source_agreement_file_id`；
- `open_source_agreement_version`。

### `project_members`

项目成员表。

核心字段：

- `id`；
- `project_id`；
- `user_id`；
- `role`：负责人、成员；
- `joined_at`；
- `left_at`。

### `project_materials`

项目材料表。

核心字段：

- `id`；
- `project_id`；
- `uploader_id`；
- `file_id`；
- `file_name`；
- `file_type`；
- `description`。

### `project_reviews`

项目审核记录表。

核心字段：

- `id`；
- `project_id`；
- `review_type`：立项、结项、进展、中断、恢复；
- `reviewer_id`；
- `decision`；
- `comment`；
- `reviewed_at`。

### `project_risk_records`

项目风控记录表。

核心字段：

- `id`；
- `project_id`；
- `reason`；
- `evidence_file_id`，可空；
- `handler_id`；
- `handled_at`；
- `impact_scope`；
- `release_condition`；
- `appeal_status`。

## 审计与通知

### `audit_logs`

审计日志表。

核心字段：

- `id`；
- `actor_id`；
- `action`；
- `target_type`；
- `target_id`；
- `before_snapshot`；
- `after_snapshot`；
- `ip`；
- `user_agent`；
- `created_at`。

### `notification_messages`

通知消息表。

核心字段：

- `id`；
- `recipient_id`；
- `channel`：站内、邮件、微信订阅消息；
- `template_code`；
- `title`；
- `content`；
- `status`；
- `sent_at`。

## 后续细化

后续实现前还需要继续细化：

- 字段类型、长度和索引名称；
- Alembic 迁移命名规范；
- 软删除和归档策略的统一实现；
- 审计快照字段是否使用 JSON；
- 文件表和 MinIO 对象元数据表设计。
