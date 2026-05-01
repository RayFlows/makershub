# core

后端核心能力目录，放置配置、数据库连接、安全、权限和日志等基础能力。

这里不放具体业务流程。

## 日志

`logging.py` 统一配置 Loguru：

- 控制台输出用于 Docker 和本地开发观察；
- 文件输出默认写入 `logs/app.log`，按天轮转并压缩保留；
- 标准库 `logging` 会桥接到 Loguru，邮件验证码 log 模式和框架日志能进入同一套日志；
- 请求日志由 `RequestContextMiddleware` 记录 method、path、状态码、耗时和 `request_id`；
- 请求日志不读取请求体，避免密码、token、验证码和上传内容进入日志。
