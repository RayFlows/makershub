# MakersHub API 契约草案

## 目标

本文档记录 MakersHub 第一阶段 API 契约草案。目标是让成员网页端、后台管理端和后续小程序共享同一套业务事实和接口语义，避免再次出现网页端、小程序端和后台管理端接口不统一的问题。

## 基本约定

### API 前缀

第一阶段正式接口统一使用：

```text
/api/v1
```

后台管理端不使用独立业务模型。后台管理端调用同一套业务接口，只是根据权限点、作用域和入口展示不同能力。

成员网页端、后台管理端和后续小程序业务页共享同一套 `/api/v1` 业务契约、状态机和业务事实。小程序不是另一套后端 API，也不能单独长出一套借用、积分、资源或审核语义；后续迁移小程序业务页时，应优先复用已经由成员网页端和后台管理端验证过的业务接口。移动端确实需要更轻的数据时，可以增加只读摘要、聚合或字段裁剪接口，但这些接口只能组合现有业务事实，不能绕过统一权限、状态流转和后端校验。

这里的“同一套业务接口”不是指成员网页端和后台管理端合并成同一个前端应用。当前工程仍然拆成
`apps/web` 和 `apps/admin` 两个前端应用：成员网页端服务普通成员自助流程，后台管理端服务审核、
管理、审计和异常处理。权限点决定后台菜单、按钮和接口授权，但后台管理端不是成员网页端简单多
渲染几个权限按钮。

端侧功能关系按包含关系处理，不按交叉关系处理：小程序用户端是成员网页端自助能力的高频轻量子集；小程序管理端是后台管理端高频轻操作子集。端侧入口、页面密度、表单拆分和交互可以不同，但提交、审核、归还、积分冻结/解冻、库存扣减/恢复等判断必须由同一套后端服务兜底。

### 统一响应

成功响应：

```json
{
  "success": true,
  "data": {},
  "message": "ok",
  "request_id": "req_xxx"
}
```

失败响应：

```json
{
  "success": false,
  "error": {
    "code": "BORROW_APPLICATION_NOT_FOUND",
    "message": "借用申请不存在",
    "details": {}
  },
  "request_id": "req_xxx"
}
```

新接口不再在响应体顶层重复返回 `code: 200`。请求是否成功由 HTTP 状态码和
`success` 表达；失败时稳定业务错误码放在 `error.code`。旧小程序和旧 Apifox
用例后续需要迁移到该响应结构，不能继续依赖旧后端的 `data.code === 200` 判断。

失败响应结构只有这一种。不同业务错误只能改变 HTTP 状态码、`error.code`、`error.message`
和 `error.details`，不能新增另一套顶层 `code`、`msg`、`data` 或旧小程序式错误 envelope。

### 分页响应

分页请求参数：

- `page`：页码，从 1 开始；
- `page_size`：每页数量；
- `sort`：排序字段；
- `order`：`asc` 或 `desc`。

分页响应：

```json
{
  "items": [],
  "page": 1,
  "page_size": 20,
  "total": 100
}
```

### 认证

认证方式：

- 小程序使用微信登录后签发访问令牌，并在首次进入时创建或找到用户主体；
- 当前最小端到端验收主线中，小程序只接入认证和邮箱绑定，不接入物资、场地、项目、活动、任务等业务接口；
- 网页端和后台管理端使用邮箱密码账号登录后签发访问令牌；
- 同一个用户主体可以挂接邮箱密码账号和微信身份，但第一版普通用户不能先注册网页账号再绑定微信；
- 第一个 `999` 是例外，可以通过受控运维初始化命令先创建邮箱密码账号，后续再绑定微信；
- 访问令牌的 `sub` 使用内部用户主键，不使用微信 `openid` 或邮箱；
- 访问令牌必须携带登录会话 ID，后端通过 `auth_sessions` 判断会话是否已退出、撤销或过期；
- 访问令牌只证明用户是谁，接口授权必须继续检查权限点和作用域。

微信登录说明：

- 小程序端调用 `wx.login` 获取一次性 `code`；
- 后端调用微信 `code2Session`，用 `appid`、`secret`、`js_code` 和 `authorization_code` 换取 `openid`、`session_key`，以及可能存在的 `unionid`；
- `openid` 是当前小程序下的用户标识，适合作为小程序登录凭证挂接字段；
- `unionid` 是同一微信开放平台账号下跨应用的用户标识，只有小程序绑定开放平台账号等条件满足时才稳定返回；
- MakersHub 内部用户主体始终使用 `users.id`，不把 `openid` 或 `unionid` 当作业务主键。

会话机制：

- 登录成功后同时返回短期 `access_token` 和长期 `refresh_token`；
- `access_token` 用于接口访问，默认有效期 120 分钟；
- `refresh_token` 用于续签令牌，默认有效期 30 天，只保存哈希到 `auth_sessions`；
- 每次调用 `/api/v1/auth/refresh` 都会轮换 refresh token，旧 refresh token 立即失效；
- 调用 `/api/v1/auth/logout` 会撤销当前 refresh token 对应的会话，携带该会话 ID 的 access token 也会被拒绝；
- 小程序可以在 access token 过期后重新执行 `wx.login`，也可以复用 refresh token 续签；正式迁移时统一封装在小程序 API 客户端里。

请求头：

```text
Authorization: Bearer <token>
```

令牌响应：

```json
{
  "access_token": "<jwt>",
  "refresh_token": "<opaque-refresh-token>",
  "token_type": "bearer",
  "expires_in": 7200,
  "expires_at": "2026-04-29T16:30:00Z",
  "refresh_expires_at": "2026-05-29T14:30:00Z",
  "user": {
    "id": 1,
    "display_name": "用户",
    "avatar_url": null,
    "status": "active",
    "email": null
  }
}
```

客户端缓存规则：

- 客户端可以缓存访问令牌，但缓存内容必须包含 `expires_at`；
- 客户端启动时不能只判断本地是否存在 token，应先检查本地过期时间，再调用 `/api/v1/auth/me` 确认后端仍接受该 token；
- `/auth/me` 或业务接口返回 `401` 且错误码为 `ACCESS_TOKEN_EXPIRED`、`INVALID_ACCESS_TOKEN`、`AUTH_SESSION_REVOKED`、`AUTH_SESSION_NOT_FOUND`、`AUTH_USER_NOT_FOUND` 时，客户端必须清理认证相关缓存；
- access token 过期时，客户端应优先调用 `/auth/refresh` 续签；refresh token 失效后再重新走登录流程；
- 清理认证缓存不等于清空全部本地存储，配置、非敏感草稿和页面偏好不应被一起删除。

### 权限

接口不直接判断 `identity_code >= 1` 这类数字大小。

接口应该检查：

- 用户是否登录；
- 用户状态是否正常；
- 用户是否拥有目标权限点；
- 用户权限是否覆盖目标作用域，例如本部门、本项目、本场地或全局。

当前实现：

- 已落地 `permissions`、`roles`、`role_permissions`、`user_role_grants`；
- 已落地 `require_permission(...)`；
- `/auth/me` 和 `/permissions/me` 返回当前用户权限摘要；
- `998/999` 默认只拥有系统兜底权限；
- `998/999` 默认拥有 `points.manual.adjust`，用于积分异常修复和受控人工调整；
- `999` 额外拥有指定或恢复 `998` 的母账号动作权限；
- 已新增 `points_manager` 角色，只能查看积分账户和流水，不能人工调整积分；
- 已新增 `points_rule_applicant`、`points_rule_reviewer`、`points_rule_manager`，用于积分规则申请、审批和固定规则维护；
- 已新增 `resource_manager` 预置角色，用于基管部常态职责打包，包含 `resources.material.manage` 和 `borrowing.application.review`；
- `resource_manager` 只是预置角色，不是接口鉴权条件；资源维护接口检查 `resources.material.manage`，借用审核和归还接口检查 `borrowing.application.review`；
- 普通业务权限仍然需要业务角色或作用域授权。

### 幂等

以下场景必须具备幂等能力：

- 邮箱验证码消费；
- 积分发放；
- 积分冻结；
- 积分解冻；
- 借用申请提交；
- 审核动作；
- 归还动作；
- 临时积分规则撤回引发的反向流水。

写接口可以通过 `Idempotency-Key` 请求头或业务唯一键实现幂等。

第一阶段借用审核和归还的幂等口径是“防重复副作用”，不是“重复请求必须返回第一次
成功响应”。也就是说，重复审核不能重复扣库存或重复冻结押金，重复归还不能重复恢复库
存或重复解冻/扣除押金；状态机已经流转后再次提交同类动作，可以返回 `409` 状态冲突。
后续如果要支持网络重试级别的同一个 `Idempotency-Key` 返回同一结果，再作为增强项补
请求重放缓存。

### 文件上传

文件上传统一走文件接口，业务表只保存文件 ID。

建议流程：

1. 客户端请求上传意图；
2. 后端登记 `pending_upload` 文件元数据并返回短期预签名 PUT URL；
3. 客户端 PUT 文件到对象存储；
4. 客户端调用完成接口，后端复核真实对象大小、类型和 sha256；
5. 业务接口只引用已经转为 `active` 的 `file_id`。

第一阶段重点支持：

- 用户头像；
- 项目材料；
- 开源协议签署文件；
- 结项材料。

当前实现：

- 已完成 `files` 元数据表、对象 key 生成和元数据登记服务；
- 已开放 `POST /api/v1/files/upload-intents` 创建短期预签名 PUT URL；
- 上传意图会统一校验 `purpose`、`content_type`、`size_bytes` 和危险后缀；
- 已开放 `POST /api/v1/files/{file_id}/complete` 复核对象真实大小、Content-Type，并记录 sha256；
- 客户端 PUT 到预签名 URL 时必须使用上传意图中的 Content-Type，否则完成复核会拒绝；
- 业务文件引用、病毒扫描或异步安全扫描仍待业务模块接入时开放。

## 第一阶段核心接口

以下路径是草案，用于表达接口边界，不代表最终路由必须逐字一致。

### 身份与登录

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/wechat/login` | 小程序微信登录 |
| `POST` | `/api/v1/auth/refresh` | 使用 refresh token 续签并轮换令牌 |
| `POST` | `/api/v1/auth/logout` | 退出登录并撤销会话 |
| `POST` | `/api/v1/auth/email/send-code` | 发送邮箱验证码 |
| `POST` | `/api/v1/auth/email/bind` | 已登录小程序用户绑定邮箱 |
| `POST` | `/api/v1/auth/email/first-login` | 网页端首次邮箱验证码登录 |
| `POST` | `/api/v1/auth/password/set` | 首次设置密码 |
| `POST` | `/api/v1/auth/password/login` | 邮箱密码登录 |
| `POST` | `/api/v1/auth/password/reset` | 邮箱验证码重置密码 |
| `POST` | `/api/v1/auth/email/change` | 更换绑定邮箱 |
| `GET` | `/api/v1/auth/me` | 获取当前登录用户和权限摘要 |

规则：

- 普通用户的账号链路以小程序微信登录为前置：先建立微信用户主体，再在小程序个人主页绑定邮箱；
- 网页端首次邮箱验证码登录只接受已经绑定到用户主体的邮箱，验证通过后强制设置密码，不创建新的普通用户主体；
- 第一版不支持“网页端先注册普通账号，再绑定微信”的流程；
- 第一个 `999` 可以通过部署初始化命令创建邮箱密码账号，不要求已有微信身份；
- `/auth/wechat/login` 生产环境必须使用微信 `code2session`；本地开发和测试环境可以使用受控 `dev_openid`，生产环境必须禁用；
- `/auth/wechat/login` 必须返回 `expires_in`、`expires_at`、`refresh_token` 和 `refresh_expires_at`，客户端据此维护登录态；
- `/auth/me` 是客户端启动态校验接口，不能被页面层绕过成本地 token 存在性判断；
- `/auth/me` 的用户摘要会返回已绑定邮箱；未绑定时为 `null`；
- `/auth/email/send-code` 已支持 `bind_email` 和 `first_login`；`bind_email` 需要当前登录用户，`first_login` 只接受已绑定但尚未设置密码的邮箱；
- 当前阶段小程序只要求接入 `wechat/login`、`refresh`、`me`、`email/send-code` 和 `email/bind`；业务页接口迁移等待成员网页端和后台控制台验证主流程后再做；
- `/auth/email/first-login` 成功后会签发登录令牌并返回 `password_required=true`，网页端必须立即进入首次设置密码流程；
- `/auth/password/set` 第一版只处理首次设置密码，已设置过密码的账号后续走修改密码或重置密码流程；
- 本地开发使用 `EMAIL_DELIVERY_MODE=log`，验证码写入服务日志，并只在 local/test/development 响应中返回 `dev_code`；
- 生产环境禁止使用 `EMAIL_DELIVERY_MODE=log`，避免明文验证码进入运行日志；
- 应用层默认对认证接口启用更严格限流，超过限制时返回 `429 RATE_LIMIT_EXCEEDED`；
- 普通接口请求体超过 `MAX_REQUEST_BODY_BYTES` 时返回 `413 REQUEST_BODY_TOO_LARGE`。
- 邮箱验证码 5 分钟有效；
- 同一邮箱 1 小时最多发送 10 次；
- 每次重新请求至少间隔 1 分钟；
- 更换邮箱需要验证旧邮箱和新邮箱；
- 第一版不允许解绑微信。

当前实现状态：

- 已完成身份域数据库模型和首批迁移；
- 已完成邮箱密码哈希工具；
- 已完成唯一 `999` 初始化服务；
- 已完成微信身份登录创建或复用用户主体的服务层逻辑；
- 已完成已登录微信用户绑定邮箱并生成待设置密码邮箱密码账号的服务层逻辑；
- 已完成 `/api/v1/auth/wechat/login`、`/api/v1/auth/refresh`、`/api/v1/auth/logout` 和 `/api/v1/auth/me` 的 HTTP 接口；
- 已完成短期 access token、长期 refresh token、会话表、refresh token 轮换和退出撤销；
- 已完成已登录用户绑定邮箱的验证码发送、限流、消费和 `/api/v1/auth/email/bind`；
- 已完成网页端首次邮箱验证码登录、首次设置密码和邮箱密码登录接口；
- 已完成绑定邮箱、首次邮箱登录、设置密码、退出登录的审计写入；
- 密码重置和更换邮箱接口仍待实现。

### 组织与成员

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/me/profile` | 查看自己的资料 |
| `PATCH` | `/api/v1/me/profile` | 修改自己的资料 |
| `GET` | `/api/v1/departments` | 查看部门列表 |
| `GET` | `/api/v1/positions` | 查看后台可维护的普通协会职务 |
| `GET` | `/api/v1/members` | 查看成员列表或花名册 |
| `GET` | `/api/v1/members/{member_id}` | 查看成员详情 |
| `PATCH` | `/api/v1/members/{member_id}` | 修改成员资料 |
| `PATCH` | `/api/v1/members/{member_id}/department` | 修改成员部门 |
| `PATCH` | `/api/v1/members/{member_id}/positions` | 修改成员职务 |

规则：

- 成员资料属于组织域，不再写回身份域 `users` 表；
- `0` 外部成员/协会会员是最低协会身份，不是后台权限点；微信首次登录创建的普通用户默认拥有 `0`；
- 旧小程序里的 `phone_num` 在新成员资料表中对应 `phone`，小程序后续适配时由 API 客户端或接口适配层映射；
- 联系邮箱属于成员资料和业务联系字段，默认取登录邮箱，但允许成员修改；修改联系邮箱不等同于更换登录邮箱；
- 后端必须校验联系邮箱格式，非法时返回 `MEMBER_PROFILE_EMAIL_INVALID`；联系邮箱不需要发送验证码确认，因为它不是登录凭证；
- 当前用户自助资料接口只能修改自己的基本资料，不能调整部门、职务和权限；
- 后台修改他人资料、部门和职务必须检查权限点并写入审计；
- 成员列表以 `users` 为根，避免微信先登录但资料未完善的用户从后台消失；
- 部门调整第一阶段采用“一个用户同一时间一个主部门”的口径，历史部门关系保留；
- 职务接口只维护普通协会职务，不维护 `998/999` 系统底层身份；
- 部门列表第一阶段要求登录访问，后续如果有公开展示需求再单独设计公开接口。

当前实现状态：

- 已完成 `departments`、`member_profiles` 和 `department_memberships` 数据模型与迁移；
- 已完成宣传部、基管部、项目部、运维部的初始部门种子；
- 已完成 `/api/v1/departments`、`/api/v1/me/profile` 的读取接口；
- 已完成 `/api/v1/me/profile` 的当前用户自助更新接口；
- 已完成 `/api/v1/positions`、`/api/v1/members`、`/api/v1/members/{member_id}`；
- 已完成后台成员资料维护、部门调整和普通协会职务调整接口；
- 后台成员写操作已接入 `organization.member.update`、`organization.member.department.assign`、`organization.member.positions.replace` 审计。

### 权限

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/permissions/me` | 获取当前用户权限摘要 |
| `GET` | `/api/v1/permissions` | 查看权限点 |
| `GET` | `/api/v1/permissions/roles` | 查看角色 |
| `GET` | `/api/v1/permissions/users/{user_id}/roles` | 查看用户角色授权记录 |
| `POST` | `/api/v1/permissions/users/{user_id}/roles` | 给用户授予业务角色 |
| `POST` | `/api/v1/permissions/role-grants/{user_role_grant_id}/revoke` | 撤销用户角色授权 |
| `POST` | `/api/v1/roles` | 创建角色，规划中 |
| `PATCH` | `/api/v1/roles/{role_id}` | 修改角色，规划中 |

说明：

- 普通业务权限由权限点和作用域控制；
- `998/999` 只处理底层系统管理和异常兜底，不默认承担普通业务审批角色；
- 唯一 `999` 初始化应优先通过脚本或受控初始化流程完成；
- 普通权限写接口不能授予或撤销 `system_operator`、`system_super_admin`；
- 第一阶段用户角色授权只开放 `global` 和 `department` 作用域，项目、资源、场地等作用域随业务域落地后再开放。

当前实现状态：

- 已完成权限数据库模型、迁移种子和默认角色；
- 已完成 `/api/v1/permissions/me`、`/api/v1/permissions`、`/api/v1/permissions/roles`；
- 已完成用户角色授权记录查询、业务角色授予和撤销接口；
- 权限写接口已接入 `permission.user_role_grant.create` 和 `permission.user_role_grant.revoke` 审计；
- 自定义角色创建、角色权限编辑和跨业务对象作用域规则仍待实现。

### 审计

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/audit/logs` | 查看最近审计日志 |

规则：

- 运行日志不等于审计日志；
- 审计日志默认只追加；
- 高风险写操作必须记录操作人、目标对象、结果、原因和必要快照。

当前实现状态：

- 已完成 `audit_logs` 数据模型和迁移；
- 已完成 `record_audit_log(...)` 服务；
- 已完成审计日志读取接口，需要 `system.audit.view`。

### 积分与账本

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/me/points/account` | 查看自己的积分账户 |
| `GET` | `/api/v1/me/points/ledger` | 查看自己的积分流水 |
| `GET` | `/api/v1/points/accounts/{user_id}` | 查看指定用户积分账户 |
| `GET` | `/api/v1/points/ledger` | 查询积分流水 |
| `POST` | `/api/v1/points/ledger/{ledger_entry_id}/reverse` | 反向修正异常流水 |
| `GET` | `/api/v1/points/rules` | 查看积分规则 |
| `POST` | `/api/v1/points/rules` | 创建固定积分规则 |
| `POST` | `/api/v1/points/rules/{rule_id}/revoke` | 撤回积分规则 |
| `GET` | `/api/v1/points/rules/temporary` | 查看临时积分规则申请 |
| `POST` | `/api/v1/points/rules/temporary` | 提交临时积分规则申请 |
| `POST` | `/api/v1/points/rules/temporary/{rule_id}/approve` | 审批临时积分规则 |
| `POST` | `/api/v1/points/rules/temporary/{rule_id}/reject` | 驳回临时积分规则 |
| `POST` | `/api/v1/points/rules/temporary/{rule_id}/revoke` | 撤回临时积分规则 |
| `POST` | `/api/v1/points/manual-adjustments` | 受控人工调整积分 |

规则：

- 业务代码不能直接改用户积分余额；
- 积分变更必须产生流水；
- 冻结、解冻、扣除、反向修正都要写入流水；
- 积分写接口必须提供 `Idempotency-Key` 或业务唯一键，防止重复发放或重复扣减；
- 后台人工调整积分只服务 `998/999` 系统兜底和异常修复，必须填写原因并写入审计；
- `points_manager` 可以查看成员积分账户和流水，但不能执行人工调整；
- `points_rule_manager` 可以维护固定规则和临时规则审批，但不自动获得 `points.manual.adjust`；
- 临时积分规则撤回默认停止后续使用，不自动追回已发积分；
- 异常追回必须通过反向流水修正。

当前实现状态：

- 已完成 `point_accounts`、`point_holds`、`point_ledger_entries` 模型和迁移；
- 已完成旧用户 0 积分账户补齐和新用户账户懒创建；
- 已完成积分服务层的人工调整、冻结、解冻、冻结转扣除和幂等保护；
- 已开放当前用户积分账户和流水接口；
- 已开放后台积分账户、流水查询和受控人工调整接口；
- 已接入 `points.manual_adjustment.create`、`points.ledger.reverse`、`points.rule.*` 和
  `points.temporary_rule.*` 审计；
- 已开放固定积分规则、临时积分规则申请/审批/驳回/撤回和反向流水修正接口；
- 冻结、解冻和冻结转扣除暂不开放 HTTP，等借用、资源和任务域接入时由服务层调用。

### 资源

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/resources/material-categories` | 查看物资分类 |
| `POST` | `/api/v1/resources/material-categories` | 新增物资分类 |
| `GET` | `/api/v1/resources/materials` | 查看物资列表 |
| `GET` | `/api/v1/resources/materials/{material_id}` | 查看物资详情 |
| `POST` | `/api/v1/resources/materials` | 新增物资 |
| `PATCH` | `/api/v1/resources/materials/{material_id}` | 编辑物资 |
| `PATCH` | `/api/v1/resources/materials/{material_id}/stock` | 调整库存 |

说明：

- 当前已落地物资分类、物资台账和库存调整；
- 场地、工位接口仍在规划中，路径暂不开放；
- 查询接口要求登录，写接口要求 `resources.material.manage`；
- 资源读取接口必须按权限兜底区分“成员可借浏览视角”和“后台台账管理视角”：没有 `resources.material.manage` 的普通成员查询物资列表时，后端默认且强制限制为 `status=available`，即使客户端手动传 `status=maintenance`、`disabled` 或 `retired`，也不能返回管理台账数据；
- 拥有 `resources.material.manage` 的用户查询物资列表时，才可以不传 `status` 查看全部状态，或按 `available`、`maintenance`、`disabled`、`retired` 筛选；
- 物资详情同样按权限兜底：普通成员只能读取 `status=available` 的物资详情；普通成员访问不存在物资或非 `available` 物资详情时，都返回 `404 MATERIAL_NOT_FOUND`，不通过 `403` 暴露该物资是否存在；拥有 `resources.material.manage` 的用户可以读取全部状态的物资详情；
- `status=available` 但 `available_quantity=0` 的物资可以只读展示为库存不足，不能作为提交或修改借用申请的合法明细；
- 业务上物资台账维护通常由基管部负责，第一阶段可通过 `resource_manager` 角色统一授予，但接口不判断部门名或角色名。

### 借用

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/borrowing/applications` | 提交借用申请 |
| `GET` | `/api/v1/borrowing/applications` | 查询借用申请 |
| `GET` | `/api/v1/borrowing/applications/{application_id}` | 查看借用详情 |
| `PATCH` | `/api/v1/borrowing/applications/{application_id}` | 修改待审核或已驳回的借用申请 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/cancel` | 取消借用申请 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/review` | 审核借用申请 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/return` | 归还处理；通过 `condition` 区分正常归还和异常归还 |

规则：

- 当前 `borrow_type` 仅支持 `material`；
- 当前最小主线只支持个人物资借用，`usage_type=project` 属于 1.5 阶段能力；
- 第一阶段个人物资借用必须提交 `expected_return_at`；旧小程序申请页已强制选择归还日期，后端提交和修改接口都必须拒绝空值；
- 提交和修改申请都必须即时校验当前物资台账：物资存在、状态可借、借用数量为正、当前可借数量足够、预计押金和申请人可用积分足够；当前可借数量不足时返回 `BORROW_MATERIAL_STOCK_NOT_ENOUGH`，不创建或更新申请；
- 普通成员只能查看、修改或取消自己的申请；修改和取消范围限待审核和已驳回申请；
- 成员端“我的借用记录”使用 `GET /api/v1/borrowing/applications?mine=true`，应展示本人全部状态：`pending_review`、`approved`、`rejected`、`cancelled`、`returned` 和 `exception_closed`；
- 成员端只对 `pending_review` 和 `rejected` 展示修改和取消动作；`approved` 表示已审核通过、等待后台处理归还，不能在成员端展示归还入口；
- 修改申请沿用旧小程序“修改原申请”的业务语义，不能要求用户取消后新建；修改 `rejected` 申请后状态回到 `pending_review`，原审核记录保留；
- 修改接口允许更新借用理由、预计归还时间和物资明细；物资明细变化时服务层可以替换当前明细快照，但必须记录操作审计，并重新计算预计押金和校验当前可用积分；
- 修改接口必须以后端判断为准，按当前物资台账重新校验物资存在、状态可借、数量合法、当前可借数量足够、预计押金和申请人可用积分；如果前端展示仍停留在旧数据，后端也必须拒绝不合法修改；
- 修改接口使用完整提交语义，请求体必须包含 `reason`、`expected_return_at` 和整份 `items`；`items` 缺失、为空或只传增量都应被拒绝，避免“保持不变、清空、漏传”三种含义混淆；
- 修改接口不允许客户端提交或修改 `borrow_type`、`usage_type`、`project_id`、`applicant_id`、`status`、`deposit_points`、`point_hold_id` 等非可修改字段；
- 修改已驳回申请后，响应中的 `reviews` 仍保留历史审核记录；端侧主状态必须按当前 `status=pending_review` 展示为待重新审核，旧驳回意见只能放在“历史审核意见”区域，不能继续当成本轮审核结论；
- 修改申请成功后响应中的 `submitted_at` 必须刷新为本次重新提交时间；`created_at` 保留原始创建时间，后台审核队列应按 `submitted_at desc, id desc` 排序；
- 借用申请请求体不接受姓名、学号、手机号、联系邮箱、年级或专业等申请人自由填写字段；服务端从当前成员资料生成申请人信息快照；
- 联系邮箱默认取登录邮箱，成员可以在资料中修改，修改联系邮箱不等同于更换登录邮箱；联系邮箱由组织域后端校验格式，但不需要验证码确认；提交和修改接口生成快照时优先使用成员资料里的联系邮箱，联系邮箱为空但登录邮箱存在时回退使用登录邮箱；
- 成员资料缺少姓名、学号、手机号、年级或专业，或联系邮箱和登录邮箱均缺失时，提交和修改接口返回 `BORROW_PROFILE_INCOMPLETE`，不创建或更新申请；如果历史数据里已有非法联系邮箱，也应按资料不完整处理，成员网页端和后续小程序端应引导用户先完善资料；
- 修改申请成功时，申请人信息快照按当时最新成员资料刷新；历史详情、审核和归还页面展示快照，不实时读取当前个人资料覆盖历史事实；
- 借用详情响应应区分申请人快照和当前联系方式：`applicant_snapshot` 表示申请事实，至少包含姓名、学号、手机号、联系邮箱、年级和专业；`applicant_current_contact` 表示当前成员资料中的手机号和联系邮箱，允许为空，仅供后台审核/归还时人工联系使用；
- 借用列表范围必须由后端兜底：普通成员调用 `GET /api/v1/borrowing/applications` 时，无论是否传 `mine=true`，都只能返回本人申请；只有拥有 `borrowing.application.review` 权限时，才允许查看全量申请列表；拥有该权限的用户如果显式传 `mine=true`，则切回本人视角；
- 借用列表字段必须由后端兜底：成员本人列表和后台全量列表都只返回摘要，不返回学号、手机号、联系邮箱或 `applicant_current_contact`，不能依赖前端隐藏敏感字段；
- 借用详情字段也必须按视角区分：普通成员查看本人详情时返回 `applicant_snapshot` 和借用明细，端侧标注为“申请时资料”，但不返回 `applicant_current_contact`；拥有 `borrowing.application.review` 权限的审核/归还人员查看详情时，默认返回 `applicant_current_contact` 作为人工联系辅助信息，不需要额外传 `include_current_contact` 参数；
- 后台审核页、归还页和历史详情页必须以 `applicant_snapshot` 作为主申请人信息；如果展示 `applicant_current_contact`，必须标注“当前成员资料”，不能把它写回申请快照、审核记录、归还记录或审计日志；
- 列表响应和列表页展示应保持旧小程序的摘要边界：学号、手机号、联系邮箱和 `applicant_current_contact` 不在列表页展示，只在详情页展示；
- 后台审核列表指后台管理端/后台主线审核控制台，不是成员中心页面；后台审核列表 UI 不使用旧小程序 `年级-专业-姓名` 的拼接字符串，应拆列展示姓名、年级、专业、提交时间、状态、类型、物资摘要和操作；申请编号可以进入详情页或审计追溯信息，不作为列表主列；
- 成员端“我的借用记录”列表是本人视角，不套用后台审核表格列；优先展示状态、提交时间、预计归还时间、物资摘要和可执行操作；
- 物资摘要由借用明细快照生成：单项显示“物资名称 x 数量”；多项显示“首件物资名称 x 数量 等 N 项”，其中 `N` 是本次申请的明细项总数；列表不展开完整物资分类、押金和每项数量；
- 小程序后续是高频轻量入口，可以接入轻量查看、提交、状态跟踪、简单审核和正常归还；物资台账维护、物资类别多层管理、库存调整、资源状态处理、复杂筛选导出和异常归还不放在小程序端，统一由浏览器端承载，其中管理类主入口为 `apps/admin`；
- 借用明细响应中的物资名称、分类名称和单件押金必须来自申请时快照，而不是实时读取当前物资台账；当前物资台账只用于提交/修改校验、审批扣库存和归还恢复库存；
- 取消接口的 `cancel_reason` 是选填字段，可以省略、传 `null` 或空字符串；服务端会规范化为空值，并仍然记录取消动作审计；
- 取消已驳回申请只是用户侧收尾，不删除 `borrow_reviews`，也不撤销审核结论；
- 拥有 `borrowing.application.review` 权限的用户可以查看全部申请、审核和处理归还；
- 后台审核工作台默认调用列表接口时传 `status=pending_review` 作为待办视角；接口仍保留状态筛选能力，用于查看全部、已通过待归还、已驳回、已取消、已归还和异常关闭；
- 后台端审核按钮只在 `pending_review` 展示；正常归还和异常归还按钮只在 `approved` 展示；
- 审核接口 `decision=reject` 时 `comment` 必填，空字符串或纯空白返回 `BORROW_FIELD_REQUIRED`；`decision=approve` 时 `comment` 选填；
- 归还动作不是普通成员自助接口；第一阶段先由后台主线审核控制台调用以验证接口、权限和状态机，后续正常归还可给小程序管理端接入；
- 虽然后端第一阶段使用同一个 `/return` 接口，但端侧必须拆成“正常归还”和“异常归还”两个明确动作；
- 正常归还动作提交前应有轻量二次确认，提示会恢复可借库存并解冻本次冻结押金，`comment` 可以为空；
- 异常归还动作提交前必须有高风险二次确认，提示会全额扣除本次冻结押金且不自动恢复可借库存，并要求填写 `comment`；
- 第一阶段后端暂不新增正常归还或异常归还的细分权限点，审核、正常归还和异常归还都暂时检查 `borrowing.application.review`；
- 正常归还按基管部 `1` 及以上的日常处理理解；异常归还按基管部 `2` 及以上、会长或对应业务负责人处理，后续权限细分时应拆成独立高风险权限点；
- 基管部常态角色 `resource_manager` 会包含该权限，但后台审核入口仍以 `borrowing.application.review` 为准；
- 审核和归还接口第一阶段必须通过状态机和积分账本幂等键防重复副作用；重复点击导致状态已经不满足审核或归还条件时，可以返回 `409`，不要求返回第一次成功结果；
- 提交申请时后端会按申请明细计算 `deposit_points`，并校验当前可借库存；若当前可用积分不足，返回 `BORROW_DEPOSIT_NOT_ENOUGH`，不创建申请；若当前可借库存不足，返回 `BORROW_MATERIAL_STOCK_NOT_ENOUGH`，不创建申请；
- 提交或修改时库存不足使用 HTTP `409`，错误响应中的 `error.details` 必须包含 `material_id`、`material_name`、`requested_quantity` 和 `available_quantity`，供成员网页端和后续小程序端展示明确提示；
- 审核通过动作会再次校验申请人的可用积分和当前可借库存，若审核时余额或库存不足，申请落为 `rejected` 并写入系统审核意见，不扣库存、不冻结押金；库存不足的系统审核意见必须包含具体物资名称、当前可借数量和申请数量；
- 审批通过扣减物资 `available_quantity` 并按物资押金冻结积分；
- 正常归还恢复库存并解冻押金；
- 损坏、遗失、消耗类归还全额扣除本次申请冻结押金，不自动恢复可借库存，后续由资源管理员做库存调整；
- 第一阶段不支持部分扣除押金，也不在归还接口开放扣除金额字段；
- 归还接口 `comment` 正常归还可选，异常归还必填；异常归还如果备注为空，返回 `BORROW_FIELD_REQUIRED`；
- `exception_closed` 是第一阶段终态，不开放撤销、重新归还或状态回退接口；误操作通过积分流水反向修正和物资库存调整兜底；
- 物资、场地、工位申请可以保留不同字段；
- 生命周期、审批、取消、归还、押金冻结和审计概念共享；
- 1.5 阶段项目借用必须关联已通过项目；
- 1.5 阶段项目借用完全免扣个人积分，但重大违规进入项目风控。

### 项目

当前状态：

- 以下路径是 1.5 阶段 API 草案，用于提前约束项目域边界。
- 当前最小端到端验收主线不开放项目接口，不要求项目立项、审核、材料上传和结项闭环。
- 其他业务如果需要项目编号、项目工位或项目借用，应先明确降级处理，不能临时在当前主线里半实现项目域。

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/projects` | 创建项目申请 |
| `GET` | `/api/v1/projects` | 查询项目列表 |
| `GET` | `/api/v1/projects/{project_id}` | 查看项目详情 |
| `PATCH` | `/api/v1/projects/{project_id}` | 编辑项目申请 |
| `POST` | `/api/v1/projects/{project_id}/submit` | 提交立项审核 |
| `POST` | `/api/v1/projects/{project_id}/review` | 审核立项 |
| `POST` | `/api/v1/projects/{project_id}/materials` | 上传项目材料 |
| `POST` | `/api/v1/projects/{project_id}/finish` | 提交结项 |
| `POST` | `/api/v1/projects/{project_id}/finish-review` | 审核结项 |
| `POST` | `/api/v1/projects/{project_id}/interrupt` | 提交或处理项目中断 |
| `POST` | `/api/v1/projects/{project_id}/risk-records` | 记录项目风控 |

规则：

- 项目负责人第一版不允许随意变更；
- 项目需要开源协议签署文件；
- 项目材料长期归档；
- 项目工位审核归入借用或资源流程，不在项目域重复建审核。

### 工作台

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/workbench/tasks` | 发布任务 |
| `GET` | `/api/v1/workbench/tasks` | 查询任务 |
| `POST` | `/api/v1/workbench/tasks/{task_id}/claim` | 领取悬赏任务 |
| `POST` | `/api/v1/workbench/tasks/{task_id}/submit` | 提交完成材料 |
| `POST` | `/api/v1/workbench/tasks/{task_id}/review` | 审核任务完成 |
| `POST` | `/api/v1/workbench/duty-messages` | 发布值班消息 |
| `POST` | `/api/v1/workbench/duty-messages/{message_id}/signup` | 报名值班 |
| `POST` | `/api/v1/workbench/duty-signups/{signup_id}/cancel` | 退出值班 |

规则：

- 指定任务发布后直接待完成；
- 悬赏任务领取后直接待完成；
- 任务完成由执行人提交，发布人审核；
- 任务发布必须引用已有积分规则，发布人不能临时填写积分数；
- 审核通过后由系统按积分规则发放积分，并回写积分流水 ID；
- 如果审核时积分规则已撤回，任务进入“规则撤回待处理”，不自动发分；
- 多场地值班报名时必须选择具体场地；
- 同一个值班消息下，一个成员只能报名一个场地。

当前实现状态：

- 已开放工作台任务发布、查询、领取、提交和审核接口；
- 已接入 `workbench.task.publish` 权限点和 `workbench_task_publisher` 角色；
- 已接入 `workbench.task.publish`、`workbench.task.claim`、`workbench.task.submit`、
  `workbench.task.review` 审计；
- 值班消息、排班、清洁任务模板和工作台导出仍待实现。

### 内容

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/content/events` | 查看活动和公告 |
| `POST` | `/api/v1/content/events` | 发布活动和公告 |
| `PATCH` | `/api/v1/content/events/{event_id}` | 编辑活动和公告 |
| `DELETE` | `/api/v1/content/events/{event_id}` | 删除活动和公告 |
| `POST` | `/api/v1/content/publicity-links` | 提交秀米链接 |
| `POST` | `/api/v1/content/publicity-links/{link_id}/review` | 审核秀米链接 |

## 错误码方向

错误码采用大写英文和业务前缀：

- `AUTH_EMAIL_CODE_EXPIRED`；
- `AUTH_INVALID_CREDENTIALS`；
- `PERMISSION_DENIED`；
- `POINT_BALANCE_NOT_ENOUGH`；
- `MEMBER_PROFILE_EMAIL_INVALID`；
- `BORROW_APPLICATION_NOT_FOUND`；
- `BORROW_PROFILE_INCOMPLETE`；
- `BORROW_MATERIAL_STOCK_NOT_ENOUGH`；
- `PROJECT_STATUS_INVALID`；
- `RESOURCE_STOCK_NOT_ENOUGH`。

## Docker 和本地联调

本地联调应通过 Docker 提供基础依赖：

- MySQL；
- MinIO；
- 后端 API；
- 成员网页端；
- 后台管理端；
- 文档站。

后续需要在 `infra/docker` 中补充 `compose` 配置，并在 `apps/docs` 中维护本地开发文档。

## 后续细化

后续实现前还需要继续细化：

- OpenAPI 生成策略；
- 前端 `packages/api-client` 的生成或手写策略；
- 文件上传是后端中转还是预签名直传；
- 列表筛选字段和排序字段；
- 具体错误码全集；
- 审计日志和业务写接口的关联方式。
