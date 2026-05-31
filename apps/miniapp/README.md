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

如果在 Windows 微信开发者工具里直接打开 WSL 的 `\\wsl.localhost\...` 路径，
新增页面文件可能出现刷新延迟。更稳妥的方式是把小程序同步到 Windows 本地镜像目录：

```bash
scripts/dev/sync-miniapp-to-windows.sh
```

然后在微信开发者工具中打开：

```text
C:\Users\Ray\Documents\New project\makershub-miniapp
```

该目录只作为 DevTools 编译镜像，源码仍以 WSL 仓库 `apps/miniapp` 为准。

当前只有认证入口先接入新版后端：

- `auth.wechatLogin`：`/api/v1/auth/wechat/login`；
- `auth.refresh`：`/api/v1/auth/refresh`；
- `auth.logout`：`/api/v1/auth/logout`；
- `auth.me`：`/api/v1/auth/me`；
- `auth.emailSendCode`：`/api/v1/auth/email/send-code`；
- `auth.emailBind`：`/api/v1/auth/email/bind`。

当前小程序已经在“我的”页增加邮箱绑定入口。开发环境下后端使用 `EMAIL_DELIVERY_MODE=log` 时，验证码会写入后端日志，并在 local/test/development 响应中返回 `dev_code`，小程序会自动填入验证码，便于本地联调。

其他业务页面仍主要指向旧的开发接口地址，后续需要按新后端 API 契约逐步改造请求封装和页面数据适配。

后续迁移业务页面时，小程序应通过 `@makershub/api-client` 定义的统一响应、错误和业务类型接入新后端，并使用小程序专用的 `wx.request` 传输适配。
迁移后的页面不能继续在页面内部手写 `wx.request`、解析旧式 `data.code === 200` 或维护 miniapp 专用业务语义。

本地微信开发者工具调试时，需要关闭“校验合法域名”，并保证本地 API 容器已经读取 `.env` 中的 `WECHAT_APP_ID` 和 `WECHAT_APP_SECRET`：

```bash
sudo docker compose --env-file .env -f infra/docker/compose.dev.yml up -d --force-recreate api
```
