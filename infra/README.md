# 基础设施配置

本目录放置 Docker、Nginx、MySQL、MinIO 等部署和基础设施配置。

业务代码不要放在这里。

## 第一阶段职责

第一阶段需要优先补齐本地开发所需的 Docker 编排：

- MySQL；
- MinIO；
- FastAPI 后端；
- 成员网页端；
- 后台管理端；
- VitePress 文档站。

Docker 配置不应和业务规则混在一起。业务规则写在 `apps/api/app/modules`，运行和部署配置写在 `infra`。

## 建议结构

```text
infra/
  docker/
    compose.dev.yml
    api.Dockerfile
    web.Dockerfile
    admin.Dockerfile
    docs.Dockerfile
    minio/
      init.sh
  nginx/
  mysql/
  minio/
```

## 当前可用入口

本地开发环境已经提供 `infra/docker/compose.dev.yml`。

在仓库根目录执行：

```bash
docker compose -f infra/docker/compose.dev.yml up --build
```

也可以只启动基础设施：

```bash
pnpm docker:infra
```

详细端口和服务说明见 `infra/docker/README.md`。
