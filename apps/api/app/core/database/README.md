# database

数据库基础设施目录，负责 SQLAlchemy ORM 基类、异步连接池、会话工厂和健康检查。

本目录负责：

- 创建统一的 AsyncEngine；
- 提供 FastAPI `get_session` 依赖；
- 提供 readiness 使用的数据库 ping；
- 应用关闭或 CLI 结束时释放连接池；
- 提供 ORM 模型复用的主键和时间戳 mixin。

本目录不负责：

- 自动建表；
- 业务事务隐式提交；
- 跨业务域的数据查询封装。

数据库结构必须通过 Alembic 迁移管理。服务层和接口层需要显式决定事务提交或回滚边界。
