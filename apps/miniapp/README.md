# 小程序端

本目录保存 MakersHub 小程序源码，已经从旧仓库 `RayFlows/MakersHub_Front-end` 导入。

## 导入说明

- 迁移来源：`RayFlows/MakersHub_Front-end`。
- 导入参考提交：`0f7b8ce`。
- 导入方式：源码快照导入到 `apps/miniapp`。
- 未导入内容：旧仓库 `.git` 目录、`project.private.config.json` 本地私有配置。
- 废弃仓库：`mini_makers` 不作为迁移来源。

## 本地打开

微信开发者工具可以直接打开 `apps/miniapp` 子目录，不需要打开整个 monorepo。

当前只有认证入口先接入新版后端：

- `auth.wechatLogin`：`/api/v1/auth/wechat/login`；
- `auth.refresh`：`/api/v1/auth/refresh`；
- `auth.logout`：`/api/v1/auth/logout`；
- `auth.me`：`/api/v1/auth/me`；
- `auth.emailSendCode`：`/api/v1/auth/email/send-code`；
- `auth.emailBind`：`/api/v1/auth/email/bind`。

当前小程序已经在“我的”页增加邮箱绑定入口。开发环境下后端使用 `EMAIL_DELIVERY_MODE=log` 时，验证码会写入后端日志，并在 local/test/development 响应中返回 `dev_code`，小程序会自动填入验证码，便于本地联调。

其他业务页面仍主要指向旧的开发接口地址，后续需要按新后端 API 契约逐步改造请求封装和页面数据适配。

本地微信开发者工具调试时，需要关闭“校验合法域名”，并保证本地 API 容器已经读取 `.env` 中的 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`：

```bash
sudo docker compose --env-file .env -f infra/docker/compose.dev.yml up -d --force-recreate api
```
