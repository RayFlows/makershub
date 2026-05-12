# MakersHub

MakersHub 是开源硬件协会平台的重构版本，采用单仓库多应用结构。

## 先从哪里看

如果你刚接回这个项目，建议只先看这几份，不要一上来把所有文档都打开：

1. [重构文档首页](apps/docs/docs/rebuild/README.md)：项目现状、阅读顺序和文档分组。
2. [需求核对清单](apps/docs/docs/rebuild/01-先读/01-需求核对清单.md)：业务口径，以它为准。
3. [第一阶段路线图](apps/docs/docs/rebuild/01-先读/02-第一阶段路线图.md)：已经做了什么、下一步做什么。
4. [后端应用代码说明](apps/api/app/README.md)：后端目录结构、请求入口和返回链路。
5. [API 契约草案](apps/docs/docs/rebuild/02-架构设计/01-API契约.md)：前端、小程序和后台共同遵守的接口格式。

## 目录

- `apps/api`：FastAPI 后端服务。
- `apps/web`：成员网页端，第一阶段优先用于验证核心业务闭环。
- `apps/admin`：新后台管理系统，直接重写旧后台。
- `apps/docs`：VitePress 文档站。
- `apps/miniapp`：小程序源码，从原 `MakersHub_Front-end` 导入，后续适配新 API。
- `packages/api-client`：前端共享 API 客户端和接口类型。
- `packages/ui`：网页端和后台端共享 UI 组件。
- `packages/config`：共享前端工程配置。
- `infra`：部署和基础设施配置。
- `scripts`：开发、初始化和运维脚本。

## 当前阶段

当前仓库已经创建重构骨架，并补齐第一阶段后端底座和部分核心业务：

- FastAPI 应用入口、健康检查、统一响应、统一错误、请求 ID；
- 双 token 认证、微信登录、本地邮箱密码登录、会话撤销；
- 组织成员资料、部门、普通协会职务维护；
- 权限点、角色、用户授权、`998/999` 系统兜底映射；
- 审计日志、运行日志、安全响应头、请求大小限制和应用层限流；
- 文件元数据和 MinIO 上传意图；
- 积分账户、冻结记录、积分流水、固定/临时积分规则和受控人工调整；
- 工作台任务发布、领取、提交、审核和审核通过后发放积分；
- 成员网页端 React/Vite 骨架，已接入登录、资料、积分和工作台任务验证页面；
- 后台管理端 React/Vite 骨架；
- VitePress 文档站；
- Docker Compose 编排 MySQL、MinIO、后端、网页端、后台端和文档站。

还没完成的第一阶段大块是：资源、借用、项目，以及小程序按新版 API 的系统适配。

## 本地启动

```bash
pnpm docker:dev
```

或：

```bash
docker compose -f infra/docker/compose.dev.yml up --build
```

启动后可访问：

- 后端健康检查：http://localhost:8000/health
- 后端接口文档：http://localhost:8000/api/v1/docs
- 成员网页端：http://localhost:5173
- 后台管理端：http://localhost:5174
- 文档站：http://localhost:5175
- MinIO 控制台：http://localhost:9001

## 后端怎么进来、怎么出去

后端进程入口是 `apps/api/app/main.py`：

1. Uvicorn 加载 `app.main:app`。
2. `create_app()` 初始化日志、中间件、异常处理器。
3. `app.include_router(api_router, prefix="/api/v1")` 挂载 V1 接口。
4. `apps/api/app/interfaces/http/v1/router.py` 汇总各业务域路由。

一次普通请求的链路是：

```text
HTTP 请求
  -> 中间件：request_id / 安全头 / 请求大小 / 限流
  -> V1 路由：interfaces/http/v1/<domain>/router.py
  -> 依赖：get_session / get_current_user / require_permission
  -> 业务服务：modules/<domain>/<capability>/service.py 或小型域的 modules/<domain>/service.py
  -> 数据访问：modules/<domain>/<capability>/repository.py 或小型域的 modules/<domain>/repository.py
  -> 数据模型：modules/<domain>/models.py
  -> success_response 或 error_response
```

登录链路是：微信或邮箱密码登录进入 `/api/v1/auth/...`，后端创建或复用 `users` 用户主体，写入 `auth_sessions`，返回短期 `access_token` 和长期 `refresh_token`。退出链路是 `/api/v1/auth/logout` 撤销当前 refresh session，后续 `/auth/me` 会拒绝已经撤销的会话。
