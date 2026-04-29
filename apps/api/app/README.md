# 后端应用代码

本目录是 FastAPI 应用主体。

- `core`：配置、数据库、安全、权限、日志等核心能力。
- `shared`：跨业务域共享的 schema、分页、响应、ID、时间工具。
- `modules`：按业务域组织的业务代码。
- `infrastructure`：MySQL、MinIO、微信等外部系统适配。
- `interfaces`：HTTP API 等对外接口层。

## 注释与工程化要求

后端 Python 文件必须遵守文档站中的 [后端代码注释与工程化规范](../../docs/docs/rebuild/backend-code-style.md)：

- 每个 Python 文件必须有文件路径头；
- 每个 Python 文件必须有中文模块级说明；
- 关键类、公共函数、路由、CLI 和迁移脚本必须写清职责和业务意图；
- 新增主要目录或业务域时必须同步维护 README。
