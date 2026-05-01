# Docker 本地开发环境

本目录放置本地开发和后续部署相关的 Docker 配置。

## 启动方式

在仓库根目录执行：

```bash
docker compose -f infra/docker/compose.dev.yml up --build
```

也可以执行：

```bash
pnpm docker:dev
```

启动后默认端口：

- 后端健康检查：http://localhost:8000/health
- 后端接口文档：http://localhost:8000/api/v1/docs
- 成员网页端：http://localhost:5173
- 后台管理端：http://localhost:5174
- 文档站：http://localhost:5175
- MinIO 控制台：http://localhost:9001

## WSL 中接入 Docker

在 Windows + WSL 开发时，推荐优先使用 Docker Desktop，并开启 WSL 集成：

1. 安装并启动 Docker Desktop。
2. 打开 Docker Desktop 设置。
3. 进入 `Resources -> WSL integration`。
4. 开启当前 Ubuntu 发行版的集成。
5. 回到 WSL 终端执行：

```bash
docker --version
docker compose version
```

如果两条命令都能输出版本号，就可以继续执行 `pnpm docker:dev`。

如果不使用 Docker Desktop，也可以在 WSL 内安装 Linux Docker Engine 和 Compose 插件。该方式需要 `sudo` 权限，并且要额外处理 daemon 自启动、用户组权限和 WSL 重启后的服务状态。除非后续明确要把 WSL 当作独立 Linux 主机维护，否则开发期优先使用 Docker Desktop 集成。

## 常用命令

```bash
pnpm docker:dev
pnpm docker:infra
pnpm docker:ps
pnpm docker:logs
pnpm docker:down
pnpm docker:down:volumes
```

- `docker:dev`：启动完整开发环境。
- `docker:infra`：只启动 MySQL、MinIO 和 MinIO 初始化任务，适合应用在 WSL 本地运行时使用。
- `docker:down`：停止开发环境，保留数据卷。
- `docker:down:volumes`：停止开发环境并删除数据卷，适合重置本地数据。

Compose 项目名固定为 `makershub-dev`，因此本地容器、网络和数据卷会带有 `makershub-dev` 前缀，方便和其他项目区分。

## 服务组成

- `mysql`：本地 MySQL 8.0，默认库名为 `makershub_dev`。
- `minio`：本地对象存储，后续用于材料、图片、附件等文件。
- `minio-init`：开发环境初始化任务，自动创建头像、公共文件、资源、项目和临时上传 bucket。
- `api`：FastAPI 后端服务。
- `web`：成员网页端。
- `admin`：后台管理端。
- `docs`：VitePress 文档站。

## 注意事项

- 当前 compose 只用于开发环境，不代表生产部署方案。
- 数据库和对象存储使用 Docker volume 保存本地数据。
- 后端容器内的 `uv` 虚拟环境固定在 `/workspace/.venv/api`，避免开发挂载覆盖依赖环境。
- 后端容器使用根目录 `uv.lock` 和 `uv sync --locked` 安装依赖，避免 Python 依赖漂移。
- 前端容器使用 `pnpm-lock.yaml` 和 `--frozen-lockfile` 安装依赖，避免容器依赖漂移。
- `minio-init` 可以重复执行，bucket 已存在时不会报错。
- 业务规则不要写入 Docker 配置，Docker 只负责运行环境编排。
- 后端日志默认同时输出到容器 stdout 和 `logs/app.log`。请求日志会带 `X-Request-ID`，
  方便把前端报错、API 响应和后端日志对齐；日志不会记录请求体。
