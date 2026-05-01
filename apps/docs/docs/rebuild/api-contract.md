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
- 网页端和后台管理端使用本地账号登录后签发访问令牌；
- 同一个用户主体可以挂接本地账号和微信身份，但第一版普通用户不能先注册网页账号再绑定微信；
- 第一个 `999` 是例外，可以通过受控运维初始化命令先创建本地账号，后续再绑定微信；
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

- 已落地 `permissions`、`roles`、`role_permissions`、`user_roles`；
- 已落地 `require_permission(...)`；
- `/auth/me` 和 `/permissions/me` 返回当前用户权限摘要；
- `998/999` 默认只拥有系统兜底权限；
- `999` 额外拥有指定或恢复 `998` 的母账号动作权限；
- 普通业务权限仍然需要业务角色或作用域授权。

### 幂等

以下场景必须具备幂等能力：

- 邮箱验证码消费；
- 积分发放；
- 积分冻结；
- 积分解冻；
- 借用申请提交；
- 审核动作；
- 临时积分规则撤回引发的反向流水。

写接口可以通过 `Idempotency-Key` 请求头或业务唯一键实现幂等。

### 文件上传

文件上传统一走文件接口，业务表只保存文件 ID。

建议流程：

1. 客户端请求上传凭证或直接上传文件；
2. 后端保存文件元数据；
3. 后端返回 `file_id` 和访问 URL；
4. 业务接口引用 `file_id`。

第一阶段重点支持：

- 用户头像；
- 项目材料；
- 开源协议签署文件；
- 结项材料。

当前实现：

- 已完成 `files` 元数据表、对象 key 生成和元数据登记服务；
- 实际上传接口、预签名 URL 和业务文件引用仍待业务模块接入时开放。

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
- 第一个 `999` 可以通过部署初始化命令创建本地账号，不要求已有微信身份；
- `/auth/wechat/login` 生产环境必须使用微信 `code2session`；本地开发和测试环境可以使用受控 `dev_openid`，生产环境必须禁用；
- `/auth/wechat/login` 必须返回 `expires_in`、`expires_at`、`refresh_token` 和 `refresh_expires_at`，客户端据此维护登录态；
- `/auth/me` 是客户端启动态校验接口，不能被页面层绕过成本地 token 存在性判断；
- `/auth/me` 的用户摘要会返回已绑定邮箱；未绑定时为 `null`；
- `/auth/email/send-code` 已支持 `bind_email` 和 `first_login`；`bind_email` 需要当前登录用户，`first_login` 只接受已绑定但尚未设置密码的邮箱；
- `/auth/email/first-login` 成功后会签发登录令牌并返回 `password_required=true`，网页端必须立即进入首次设置密码流程；
- `/auth/password/set` 第一版只处理首次设置密码，已设置过密码的账号后续走修改密码或重置密码流程；
- 本地开发使用 `EMAIL_DELIVERY_MODE=log`，验证码写入服务日志，并只在 local/test/development 响应中返回 `dev_code`；
- 生产环境禁止使用 `EMAIL_DELIVERY_MODE=log`，避免明文验证码进入运行日志；
- 邮箱验证码 5 分钟有效；
- 同一邮箱 1 小时最多发送 10 次；
- 每次重新请求至少间隔 1 分钟；
- 更换邮箱需要验证旧邮箱和新邮箱；
- 第一版不允许解绑微信。

当前实现状态：

- 已完成身份域数据库模型和首批迁移；
- 已完成本地账号密码哈希工具；
- 已完成唯一 `999` 初始化服务；
- 已完成微信身份登录创建或复用用户主体的服务层逻辑；
- 已完成已登录微信用户绑定邮箱并生成待设置密码本地账号的服务层逻辑；
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
| `GET` | `/api/v1/members` | 查看成员列表或花名册 |
| `GET` | `/api/v1/members/{member_id}` | 查看成员详情 |
| `PATCH` | `/api/v1/members/{member_id}` | 修改成员资料 |
| `GET` | `/api/v1/departments` | 查看部门列表 |
| `PATCH` | `/api/v1/members/{member_id}/department` | 修改成员部门 |
| `PATCH` | `/api/v1/members/{member_id}/positions` | 修改成员职务 |

规则：

- 成员资料属于组织域，不再写回身份域 `users` 表；
- 旧小程序里的 `phone_num` 在新成员资料表中对应 `phone`，小程序后续适配时由 API 客户端或接口适配层映射；
- 当前用户自助资料接口只能修改自己的基本资料，不能调整部门、职务和权限；
- 后台修改他人资料、部门和职务必须接入权限点后再开放；
- 部门列表第一阶段要求登录访问，后续如果有公开展示需求再单独设计公开接口。

当前实现状态：

- 已完成 `departments`、`member_profiles` 和 `department_memberships` 数据模型与迁移；
- 已完成宣传部、基管部、项目部、运维部的初始部门种子；
- 已完成 `/api/v1/departments`、`/api/v1/me/profile` 的读取接口；
- 已完成 `/api/v1/me/profile` 的当前用户自助更新接口；
- 成员列表、成员详情、后台成员资料维护、部门调整和职务调整仍待接入权限系统后实现。

### 权限

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/permissions/me` | 获取当前用户权限摘要 |
| `GET` | `/api/v1/permissions` | 查看权限点 |
| `GET` | `/api/v1/permissions/roles` | 查看角色 |
| `POST` | `/api/v1/roles` | 创建角色 |
| `PATCH` | `/api/v1/roles/{role_id}` | 修改角色 |
| `POST` | `/api/v1/users/{user_id}/roles` | 给用户授予角色或权限作用域 |
| `DELETE` | `/api/v1/users/{user_id}/roles/{user_role_id}` | 撤销用户角色 |

说明：

- 普通业务权限由权限点和作用域控制；
- `998/999` 只处理底层系统管理和异常兜底，不默认承担普通业务审批角色；
- 唯一 `999` 初始化应优先通过脚本或受控初始化流程完成。

当前实现状态：

- 已完成权限数据库模型、迁移种子和默认角色；
- 已完成 `/api/v1/permissions/me`、`/api/v1/permissions`、`/api/v1/permissions/roles`；
- 权限写接口尚未开放，必须先接入权限变更审计。

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
| `POST` | `/api/v1/points/rules/temporary` | 提交临时积分规则申请 |
| `POST` | `/api/v1/points/rules/temporary/{rule_id}/approve` | 审批临时积分规则 |
| `POST` | `/api/v1/points/rules/temporary/{rule_id}/revoke` | 撤回临时积分规则 |
| `POST` | `/api/v1/points/manual-adjustments` | 受控人工调整积分 |

规则：

- 业务代码不能直接改用户积分余额；
- 积分变更必须产生流水；
- 冻结、解冻、扣除、反向修正都要写入流水；
- 临时积分规则撤回默认停止后续使用，不自动追回已发积分；
- 异常追回必须通过反向流水修正。

### 资源

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/resources/materials` | 查看物资列表 |
| `GET` | `/api/v1/resources/materials/{material_id}` | 查看物资详情 |
| `POST` | `/api/v1/resources/materials` | 新增物资 |
| `PATCH` | `/api/v1/resources/materials/{material_id}` | 编辑物资 |
| `PATCH` | `/api/v1/resources/materials/{material_id}/stock` | 调整库存 |
| `GET` | `/api/v1/resources/sites` | 查看场地列表 |
| `POST` | `/api/v1/resources/sites` | 新增场地 |
| `PATCH` | `/api/v1/resources/sites/{site_id}` | 编辑场地 |
| `GET` | `/api/v1/resources/workstations` | 查看工位列表 |
| `POST` | `/api/v1/resources/workstations` | 新增工位 |
| `PATCH` | `/api/v1/resources/workstations/{workstation_id}` | 编辑工位 |

### 借用

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/borrowing/applications` | 提交借用申请 |
| `GET` | `/api/v1/borrowing/applications` | 查询借用申请 |
| `GET` | `/api/v1/borrowing/applications/{application_id}` | 查看借用详情 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/cancel` | 取消借用申请 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/review` | 审核借用申请 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/return` | 确认归还 |
| `POST` | `/api/v1/borrowing/applications/{application_id}/close-exception` | 异常关闭 |

规则：

- 物资、场地、工位申请可以保留不同字段；
- 生命周期、审批、取消、归还、押金冻结和审计概念共享；
- 项目借用必须关联已通过项目；
- 项目借用完全免扣个人积分，但重大违规进入项目风控。

### 项目

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
- 多场地值班报名时必须选择具体场地；
- 同一个值班消息下，一个成员只能报名一个场地。

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
- `BORROW_APPLICATION_NOT_FOUND`；
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
