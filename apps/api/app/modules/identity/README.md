# 身份与登录

负责用户登录身份、本地账号、微信身份、会话、令牌和初始化超级管理员。

不负责成员部门、职务和业务权限授予。

## 已落地的基础能力

- `users`：用户主体表；
- `local_accounts`：邮箱和密码账号表；
- `wechat_accounts`：微信身份表；
- `email_verification_codes`：邮箱验证码记录表；
- 密码哈希和校验工具；
- 初始化唯一 `999` 超级管理员的服务。

## 初始化 999

在 Docker 开发环境中执行：

```bash
docker compose -f infra/docker/compose.dev.yml exec api sh -lc \
  'INITIAL_SUPER_ADMIN_PASSWORD="<change-me>" uv run python -m app.cli bootstrap-super-admin --email admin@example.com'
```

该命令会创建一个用户主体、本地账号，并授予 `999` 职务。系统中已经存在有效 `999` 时，命令会拒绝继续创建。

生产环境不要把真实初始密码写入仓库或 shell 历史，应由部署平台 secret 或临时受控环境变量传入。

## 后续待实现

- 邮箱验证码发送、限流和消费；
- 首次邮箱登录；
- 密码登录和访问令牌；
- 微信登录和微信身份挂接；
- `/api/v1/auth/me` 当前用户摘要。
