# system

系统 V1 接口目录，负责健康检查和后续服务状态类 HTTP 入口。

本目录负责：

- `/api/v1/health` readiness 检查；
- 检查数据库、MinIO 等关键依赖；
- 在依赖异常时返回结构化 degraded 结果和 503 状态码。

本目录不负责：

- 业务数据检查；
- 监控告警发送；
- 替代部署平台的 liveness probe。

根路径 `/health` 只证明 API 进程存活；`/api/v1/health` 用于判断服务是否可以接收业务流量。
