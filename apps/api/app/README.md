# 后端应用代码

本目录是 FastAPI 应用主体。

## 目录分层

| 目录 | 负责什么 | 常看文件 |
| --- | --- | --- |
| `main.py` | FastAPI 应用入口，注册中间件、异常处理和总路由 | `main.py` |
| `core` | 配置、数据库、安全、权限、日志、错误处理等核心底座 | `core/README.md` |
| `interfaces` | HTTP API 等对外接口层，负责请求参数、鉴权依赖和响应转换 | `interfaces/http/v1/router.py` |
| `modules` | 按业务域组织的业务代码，负责业务事实和业务规则 | `modules/README.md` |
| `infrastructure` | 微信、MinIO、邮件等外部系统适配 | `infrastructure/README.md` |
| `shared` | 跨业务域共享的响应、分页、时间、ID 等小工具 | `shared/README.md` |

## 请求链路

一次请求不是直接进业务模块，而是按下面的路径走：

```text
app/main.py
  -> RequestContextMiddleware / SecurityHeadersMiddleware / RateLimitMiddleware
  -> interfaces/http/v1/router.py
  -> interfaces/http/v1/<domain>/router.py
  -> interfaces/http/dependencies.py
  -> modules/<domain>/<capability>/service.py 或 modules/<domain>/service.py
  -> modules/<domain>/<capability>/repository.py 或 modules/<domain>/repository.py
  -> modules/<domain>/models.py
```

各层边界：

- `router.py`：只处理 HTTP 契约、依赖注入、权限检查、响应组装和必要审计；
- `schemas.py`：只描述请求和响应模型；
- `service.py`：处理业务规则，例如积分不能透支、微信用户如何创建、权限如何判断；
- `repository.py`：只封装数据库查询和写入，不决定业务是否允许；
- `models.py`：只描述数据库表和关系；
- `migrations/versions`：描述数据库结构如何从一个版本变到下一个版本。

## 登录和退出链路

登录进入：

```text
小程序 wx.login 或网页邮箱密码
  -> /api/v1/auth/...
  -> modules/identity/accounts + modules/identity/sessions
  -> users / wechat_accounts / email_password_accounts / auth_sessions
  -> 返回 access_token + refresh_token
```

后续访问：

```text
Authorization: Bearer <access_token>
  -> get_current_user
  -> 读取 token 中的 user_id 和 session_id
  -> 确认用户存在、状态正常、会话未撤销
  -> 业务接口继续检查权限点
```

退出登录：

```text
/api/v1/auth/logout
  -> 撤销当前 auth_sessions 记录
  -> 旧 refresh_token 失效
  -> 携带该 session_id 的 access_token 也会在 /auth/me 或受保护接口中被拒绝
```

## 当前主要业务域

- `identity`：用户主体、微信身份、邮箱密码账号、验证码、登录会话；
- `organization`：成员资料、部门、普通协会职务；
- `permissions`：在 `core/permissions`，负责权限点、角色和用户授权；
- `audit`：审计日志；
- `files`：文件元数据和上传意图；
- `points`：积分账户、冻结记录、积分流水和受控人工调整。

`resources`、`borrowing`、`projects`、`workbench` 等目录目前主要是边界说明，完整业务还没落地。

## 注释与工程化要求

后端 Python 文件必须遵守文档站中的 [后端代码注释与工程化规范](../../docs/docs/rebuild/03-工程运维/02-后端代码规范.md)：

- 每个 Python 文件必须有文件路径头；
- 每个 Python 文件必须有中文模块级说明；
- 关键类、公共函数、路由、CLI 和迁移脚本必须写清职责和业务意图；
- 新增主要目录或业务域时必须同步维护 README。
