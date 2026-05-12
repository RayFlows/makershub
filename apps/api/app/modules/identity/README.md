# 身份与登录

身份域负责“用户是谁、通过什么凭证登录、当前会话是否有效”。它是微信小程序、
成员网页端和后台管理端共享的登录基础。

本域不负责成员部门、协会职务、业务角色和权限授予；这些能力分别由 `organization`
和 `core/permissions` 处理。跨域代码如果需要确认当前用户，只能读取用户主体或调用
会话校验能力，不能在身份域里顺手完成组织或权限变更。

## 关键业务约束

- 普通用户第一版必须先通过小程序微信无感登录建立内部用户主体；
- 小程序用户在个人主页绑定邮箱后，系统才创建邮箱密码登录入口；
- 网页端首次登录只接受“已经绑定邮箱、尚未设置密码”的账号，并强制设置密码；
- 第一版不支持普通用户先从网页端注册一个孤立账号再绑定微信；
- 第一个 `999` 是唯一例外，只能通过受控 CLI 初始化，服务部署和灾备；
- `openid` 是当前小程序下的微信身份标识，`unionid` 可空，不能作为启动硬依赖；
- access token 必须绑定服务端 `auth_sessions`，会话被撤销后旧 access token 也要失效。

## 当前入口

身份域已经拆成二级能力模块。根目录不再保留 `service.py` 和 `repository.py`，调用方应按
业务意图导入明确入口：

| 能力 | 导入入口 | 典型调用方 |
| --- | --- | --- |
| 微信登录、邮箱绑定、密码登录 | `app.modules.identity.accounts` | 认证 HTTP 路由 |
| access/refresh token 和会话撤销 | `app.modules.identity.sessions` | 认证 HTTP 路由、当前用户依赖 |
| 邮箱验证码签发和消费 | `app.modules.identity.email_codes` | 认证 HTTP 路由、账号能力 |
| 唯一 `999` 初始化 | `app.modules.identity.bootstrap` | `app.cli` 运维命令 |
| 用户主体和登录凭证数据库读写 | `app.modules.identity.repositories` | 身份域内部服务、少量跨域只读校验 |
| 结果对象和值校验 | `app.modules.identity.types`、`app.modules.identity.utils` | 身份域内部服务和测试 |

## 目录结构

```text
identity/
  models.py                     # 用户主体、微信账号、邮箱密码账号、会话和验证码模型
  types.py                      # 服务层返回结构
  utils.py                      # 邮箱、微信标识、密码和时间校验工具
  accounts/
    README.md                   # 账号能力边界
    wechat.py                   # 小程序微信登录和 0 基础身份授予
    email_password.py           # 邮箱绑定、首次登录、设置密码和密码登录
  email_codes/
    README.md                   # 邮箱验证码能力边界
    service.py                  # 验证码签发、限流、哈希和消费
  sessions/
    README.md                   # 登录会话能力边界
    service.py                  # access/refresh token、会话轮换和撤销
  bootstrap/
    README.md                   # 初始化 999 能力边界
    service.py                  # 唯一 999 初始化
  repositories/
    README.md                   # 身份仓储边界
    accounts.py                 # 微信账号和邮箱密码账号数据库操作
    email_codes.py              # 验证码数据库操作
    sessions.py                 # 登录会话数据库操作
    base.py                     # 用户主体和职务查询等共享仓储能力
```

## 已落地能力

- `users`：内部用户主体；
- `wechat_accounts`：小程序微信身份；
- `email_password_accounts`：邮箱密码登录入口，支持“已绑定邮箱但未设置密码”的首次登录状态；
- `email_verification_codes`：邮箱验证码记录，保存哈希，不保存明文验证码；
- `auth_sessions`：服务端登录会话，保存 refresh token 哈希并支持撤销；
- 微信登录创建或复用用户主体，并给首次微信用户授予 `0` 外部成员基础身份；
- 小程序端绑定邮箱后生成邮箱密码账号；
- 网页端首次邮箱验证码登录、首次设置密码和后续邮箱密码登录；
- access token + refresh token 双令牌签发、刷新和退出登录撤销；
- 唯一 `999` 超级管理员 CLI 初始化。

## 调用链路

微信登录：

```text
/api/v1/auth/wechat/login
  -> identity.accounts.login_wechat_identity
  -> identity.sessions.issue_auth_token_pair
  -> users / wechat_accounts / auth_sessions
```

绑定邮箱：

```text
/api/v1/auth/email/send-code
  -> identity.email_codes.issue_email_verification_code

/api/v1/auth/email/bind
  -> identity.accounts.bind_email_with_code
  -> email_verification_codes / email_password_accounts
```

网页端登录：

```text
首次登录:
  /api/v1/auth/email/first-login
    -> identity.accounts.complete_first_login_with_code
    -> identity.sessions.issue_auth_token_pair

密码登录:
  /api/v1/auth/password/login
    -> identity.accounts.login_email_password_account_with_password
    -> identity.sessions.issue_auth_token_pair
```

当前用户解析：

```text
Authorization: Bearer <access_token>
  -> interfaces/http/dependencies.py
  -> identity.sessions.validate_auth_session
  -> identity.repositories.IdentityRepository.get_user_by_id
```

## 维护规则

- 不要恢复根目录 `service.py` 或 `repository.py`；
- 新增密码重置、更换邮箱、登录失败限制时，放入对应二级能力模块；
- 如果出现跨多个能力的复杂编排，应新增明确的应用用例模块，不要重新堆成根级大文件；
- 仓储层不提交事务，只封装查询和写入；
- 普通业务域不能直接修改身份域表；确实需要用户存在性校验时，优先调用公开服务或统一仓储入口；
- 涉及登录、绑定、撤销、999 初始化等安全事件时，HTTP 层或 CLI 必须写审计日志。

## 初始化 999

在 Docker 开发环境中执行：

```bash
docker compose -f infra/docker/compose.dev.yml exec api sh -lc \
  'INITIAL_SUPER_ADMIN_PASSWORD="<change-me>" uv run python -m app.cli bootstrap-super-admin --email admin@example.com'
```

该命令会创建一个用户主体、邮箱密码账号，并授予 `999` 职务。系统中已经存在有效 `999` 时，命令会拒绝继续创建。

生产环境不要把真实初始密码写入仓库或 shell 历史，应由部署平台 secret 或临时受控环境变量传入。

## 后续待实现

- 密码重置；
- 更换绑定邮箱；
- 登录失败次数限制和异常登录审计。
