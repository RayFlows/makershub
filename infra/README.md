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

## 公共静态资源

邮件品牌图、公开宣传图等可以放在 MinIO public bucket 中，再由静态域名反向代理出来。

当前提供了示例配置：

- `infra/nginx/static-minio.example.conf`

推荐生产入口：

```text
https://static.scumaker.com/public/brand/SCUMAKER_logowithtext_email.png
  -> makershub-public-prod/brand/SCUMAKER_logowithtext_email.png
```

只有 public bucket 可以这样暴露。物资材料、项目附件、审批材料等私有文件仍然必须走后端鉴权和短期签名 URL。
