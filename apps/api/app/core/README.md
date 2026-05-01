# core

后端核心能力目录，放置配置、数据库连接、安全、权限和日志等基础能力。

这里不放具体业务流程。

## 日志

`logging/` 统一配置 Loguru：

- 控制台输出用于 Docker 和本地开发观察；
- 文件输出按用途分流，默认写入 `logs/app.log`、`logs/error.log`、`logs/request.log`、`logs/debug.log`；
- `app.log` 只记录普通运行信息和 warning，默认保留 30 天；
- `error.log` 记录所有 `ERROR/CRITICAL`，默认保留 180 天，便于线上事故复盘；
- `request.log` 记录 HTTP 请求开始、结束和异常，默认保留 30 天；
- `debug.log` 只记录 `DEBUG`，默认保留 7 天；生产环境默认不写，除非显式配置 `LOG_DEBUG_FILE_ENABLED=true`；
- 所有文件默认按天轮转并压缩，保留周期通过 `LOG_RETENTION`、`LOG_ERROR_RETENTION`、`LOG_REQUEST_RETENTION`、`LOG_DEBUG_RETENTION` 调整；
- 标准库 `logging` 会桥接到 Loguru，邮件验证码 log 模式和框架日志能进入同一套日志；
- 请求日志由 `RequestContextMiddleware` 记录 method、path、状态码、耗时和 `request_id`；
- 请求日志不读取请求体或 query string，避免密码、token、验证码和上传内容进入日志。

## 错误处理

`errors/` 统一处理业务异常、参数校验错误、HTTP 框架错误和未知异常：

- 业务层抛出 `AppError`，由全局 handler 转为统一错误响应；
- 500 级业务异常和未知异常会写入运行日志，并携带 `request_id`；
- 响应中不暴露堆栈、SQL、密钥或内部连接信息；
- 运行日志只用于排查，关键业务修改仍需写入审计日志。

## 权限

`permissions/` 落地权限点注册表、权限数据库模型、角色授权服务和 HTTP 权限依赖：

- 业务代码引用稳定权限点 code；
- 不允许继续用身份数字大小比较做鉴权；
- `require_permission(...)` 负责把权限拒绝转换为统一 403；
- `998/999` 默认只拥有系统兜底权限，不自动拥有普通业务权限；
- `999` 额外拥有指定或恢复 `998` 的母账号动作权限；
- 权限变更写接口必须先接入审计后再开放。

## HTTP 安全边界

`security/` 中的 HTTP 中间件负责所有接口的基础安全边界：

- 默认写入 `X-Content-Type-Options`、`X-Frame-Options`、`Referrer-Policy`、
  `Cross-Origin-Resource-Policy`、`Permissions-Policy` 等安全头；
- 生产环境默认写入 HSTS，本地开发默认关闭；
- 普通接口默认限制 `Content-Length`，避免非上传接口被大请求体消耗资源；
- 默认启用进程内限流，认证相关接口使用更严格的限流桶；
- 多实例生产环境仍必须在网关、Redis 或云厂商安全产品侧配置集中限流。

这些能力是应用层兜底，不替代 HTTPS 终止、WAF、负载均衡、集中限流和安全告警。

## 工程化守卫

后端提交前必须通过 Ruff 和测试中的工程化守卫：

- Ruff 负责基础语法、导入排序、常见 bug、pytest 写法和时区风险检查；
- `tests/test_engineering_standards.py` 检查 Python 文件头、模块级说明、基础设施目录 README；
- 业务代码必须通过 `app.shared.time.utc_now()` 获取当前 UTC 时间，不能在各模块直接调用 `datetime.now(UTC)`；
- 这些规则是维护底线，不随具体业务迭代放宽。
