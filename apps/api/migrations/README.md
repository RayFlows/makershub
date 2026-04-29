# 数据库迁移

本目录放置 Alembic 数据库迁移脚本。Alembic 配置文件位于 `apps/api/alembic.ini`，迁移脚本版本目录为 `migrations/versions`。

常用命令：

```bash
uv run --project apps/api alembic -c apps/api/alembic.ini revision --autogenerate -m "create identity tables"
uv run --project apps/api alembic -c apps/api/alembic.ini upgrade head
```

如果使用 Docker 开发环境，推荐在 `api` 容器内执行迁移，这样 `DATABASE_URL` 会直接使用 Compose 网络中的 `mysql` 主机名：

```bash
docker compose -f infra/docker/compose.dev.yml exec api uv run alembic -c alembic.ini current
docker compose -f infra/docker/compose.dev.yml exec api uv run alembic -c alembic.ini upgrade head
```

当前首批迁移为：

```text
20260429_0001_create_identity_tables.py
```

它创建身份、微信账号、本地账号、邮箱验证码、职务和用户职务关系表，并初始化基础职务数据。
