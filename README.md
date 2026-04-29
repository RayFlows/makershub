# MakersHub

MakersHub 是开源硬件协会平台的重构版本，采用单仓库多应用结构。

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

当前仓库已经创建重构骨架，并补齐第一阶段本地开发入口：

- FastAPI 最小应用和健康检查；
- 成员网页端 React/Vite 骨架；
- 后台管理端 React/Vite 骨架；
- VitePress 文档站；
- Docker Compose 编排 MySQL、MinIO、后端、网页端、后台端和文档站。

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
