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

当前 `config.js` 仍指向旧的开发接口地址，后续需要按新后端 API 契约改造请求封装和页面数据适配。第一阶段仍以网页端和 API 验证核心业务逻辑，小程序在接口稳定后再逐步接入。
