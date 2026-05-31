# API 客户端

本包放置前端共享 API 客户端和接口类型。

目标是让成员网页端、后台管理端和后续小程序尽量使用同一套接口契约。

## 第一阶段职责

`@makershub/api-client` 是端侧和 `/api/v1` 后端之间的共享调用层。第一阶段不要让
`apps/web`、`apps/admin` 和 `apps/miniapp` 分别维护三套请求、错误、令牌和权限逻辑。

本包应收敛：

- 新版响应信封解析：`success`、`data`、`error.code`、`error.message`、`error.details`、`request_id`；
- `ApiRequestError` 等统一错误对象，保留 HTTP 状态码、业务错误码、错误详情和请求 ID；
- 认证接口：邮箱验证码登录、密码登录、令牌续签、退出、`/auth/me`；
- 权限接口：`/permissions/me` 和前端权限摘要类型；
- 会话辅助能力：access token 过期判断、refresh token 续签、会话清理；
- 可注入的存储适配：web/admin 可以使用不同 `localStorage` key，小程序使用微信 storage，但共享同一套会话语义；
- 可注入的传输适配：web/admin 使用 `fetch`，小程序后续使用 `wx.request`；
- 第一阶段业务 API：成员资料、积分账户和流水、物资资源、物资借用、审核、归还、审计读取；
- 稳定业务常量和轻量展示映射：错误码、借用状态、物资状态、归还结果、积分业务类型等。

## 不放什么

本包不放 React 页面、Ant Design 表格、路由菜单、小程序页面结构、弹窗交互和具体表单布局。

UI 组件放在 `@makershub/ui`。页面流程仍由 `apps/web`、`apps/admin` 和 `apps/miniapp`
按各自入口组织。

## 当前实现状态

当前已经抽出第一版共享调用层：

- `src/http.ts`：请求传输、`fetch` 适配和新版响应信封解析；
- `src/errors.ts`：`ApiRequestError` 和错误详情；
- `src/session.ts`：认证存储适配、`StoredAuth` 和令牌过期判断；
- `src/client.ts`：认证、权限、成员资料、积分和工作台任务 API；
- `src/domain.ts`：工作台任务状态和可见范围标签。

`apps/web/src/api.ts` 和 `apps/web/src/auth-storage.ts` 现在只保留成员网页端自己的
base URL 与 storage key 配置。

`apps/admin` 接入真实登录、`/auth/me`、`/permissions/me` 和后台审核页前，不应重新写一套
后台专用 API 客户端。

小程序当前只验收新版登录和邮箱绑定。业务页面后续迁移时，不能继续在页面内手写
`wx.request` 并判断旧式 `data.code === 200`，应通过小程序传输适配进入同一套新版契约。
