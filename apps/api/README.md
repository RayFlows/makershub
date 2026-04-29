# 后端服务

本目录放置 MakersHub 的 FastAPI 后端服务。

后端按业务域组织代码，核心业务位于 `app/modules`，不要再按旧项目的 `models/routes/services` 三层平铺方式扩展。

## 当前底座

- `app/core/config`：环境变量和运行配置；
- `app/core/database`：SQLAlchemy 异步引擎、会话和数据库健康检查；
- `app/core/errors`：应用异常和统一错误响应；
- `app/shared`：统一响应、分页结构和请求上下文；
- `app/interfaces/http/v1`：HTTP V1 路由注册入口；
- `migrations`：Alembic 迁移脚本目录。

`/health` 是轻量存活检查，供容器健康检查使用。

`/api/v1/health` 是就绪检查，会检查数据库和 MinIO，并返回统一响应结构。
