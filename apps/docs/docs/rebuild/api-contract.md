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

- 网页端和后台管理端使用本地账号登录后签发访问令牌；
- 小程序使用微信登录后签发访问令牌；
- 同一个用户主体可以挂接本地账号和微信身份；
- 访问令牌只证明用户是谁，接口授权必须继续检查权限点和作用域。

请求头：

```text
Authorization: Bearer <token>
```

### 权限

接口不直接判断 `identity_code >= 1` 这类数字大小。

接口应该检查：

- 用户是否登录；
- 用户状态是否正常；
- 用户是否拥有目标权限点；
- 用户权限是否覆盖目标作用域，例如本部门、本项目、本场地或全局。

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

## 第一阶段核心接口

以下路径是草案，用于表达接口边界，不代表最终路由必须逐字一致。

### 身份与登录

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `POST` | `/api/v1/auth/wechat/login` | 小程序微信登录 |
| `POST` | `/api/v1/auth/email/send-code` | 发送邮箱验证码 |
| `POST` | `/api/v1/auth/email/first-login` | 网页端首次邮箱验证码登录 |
| `POST` | `/api/v1/auth/password/set` | 首次设置密码 |
| `POST` | `/api/v1/auth/password/login` | 邮箱密码登录 |
| `POST` | `/api/v1/auth/password/reset` | 邮箱验证码重置密码 |
| `POST` | `/api/v1/auth/email/change` | 更换绑定邮箱 |
| `GET` | `/api/v1/auth/me` | 获取当前登录用户和权限摘要 |

规则：

- 邮箱验证码 5 分钟有效；
- 同一邮箱 1 小时最多发送 10 次；
- 每次重新请求至少间隔 1 分钟；
- 更换邮箱需要验证旧邮箱和新邮箱；
- 第一版不允许解绑微信。

当前实现状态：

- 已完成身份域数据库模型和首批迁移；
- 已完成本地账号密码哈希工具；
- 已完成唯一 `999` 初始化服务；
- 本节接口仍待实现。

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

### 权限

| 方法 | 路径 | 用途 |
| --- | --- | --- |
| `GET` | `/api/v1/permissions` | 查看权限点 |
| `GET` | `/api/v1/roles` | 查看角色 |
| `POST` | `/api/v1/roles` | 创建角色 |
| `PATCH` | `/api/v1/roles/{role_id}` | 修改角色 |
| `POST` | `/api/v1/users/{user_id}/roles` | 给用户授予角色或权限作用域 |
| `DELETE` | `/api/v1/users/{user_id}/roles/{user_role_id}` | 撤销用户角色 |

说明：

- 普通业务权限由权限点和作用域控制；
- `998/999` 只处理底层系统管理和异常兜底；
- 唯一 `999` 初始化应优先通过脚本或受控初始化流程完成。

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
