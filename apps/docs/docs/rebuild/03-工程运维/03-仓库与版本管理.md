# 仓库、迁移与版本管理

本文档记录 MakersHub 重构后的 GitHub 仓库归属、旧仓库处理方式、分支与提交规则、版本号、镜像标签和发布记录约定。

它面向后续开发和运维人员。目标是让代码、文档、环境配置和发布过程都能追踪到同一个版本来源，避免出现“本地能跑、服务器不知道是哪一版”的情况。

## 总体结论

MakersHub 后续采用单仓库多应用结构。

主仓库建议固定为：

```text
RayFlows/makershub
```

本地目录也使用：

```text
/home/ray/work/makershub
```

仓库名、目录名、根项目名都统一使用 `makershub`。不再继续使用 `makershub-v2` 作为长期名称。

## GitHub 仓库关系

| 仓库 | 定位 | 后续处理 |
| --- | --- | --- |
| `RayFlows/makershub` | 新系统主仓库 | 新建空仓库后作为唯一主线，存放后端、网页端、后台端、文档站、小程序、Docker 和运维配置 |
| `RayFlows/makershub-backend` | 旧后端仓库 | 作为参考仓库保留，不再承接新系统主线开发 |
| `RayFlows/MakersHub_Front-end` | 旧小程序仓库 | 源码已经导入 `apps/miniapp`，后续在主仓内适配新 API |
| `RayFlows/mini_makers` | 废弃仓库 | 不迁移、不维护、不作为参考基线 |

如果后续 GitHub 上还有其他实验仓库，也应先在本文档登记定位，再决定是否迁移，避免多个仓库同时演化同一套业务。

## 单仓库策略

主仓库包含：

- `apps/api`：FastAPI 后端；
- `apps/web`：成员网页端；
- `apps/admin`：后台管理端；
- `apps/docs`：文档站；
- `apps/miniapp`：微信小程序；
- `packages/*`：前端共享包；
- `infra/*`：Docker、Nginx、数据库、对象存储和部署配置；
- `scripts/*`：开发、初始化和运维脚本。

这样做的好处是：

- API 契约、前端调用、数据库迁移和文档可以一起变更；
- 本地开发环境和生产部署配置能跟随代码版本管理；
- 运维排查时只需要确认一个 Git commit；
- 后续发布时可以用同一个版本号描述一组应用的组合状态。

第一阶段不建议把后端、网页端、后台端、小程序拆成多个新仓库。等系统稳定、团队边界清晰、发布节奏确实不同之后，再考虑拆分。

## 旧仓库迁移规则

### 旧后端

`makershub-backend` 只作为参考来源。

后端新代码在 `apps/api` 中按业务域重写，不直接把旧项目结构整体搬入。旧后端中已经验证过的业务规则、接口命名和数据字段，可以在实现新模块时参考，但需要落到新的数据库设计、API 契约和权限模型中。

### 旧小程序

`MakersHub_Front-end` 是旧小程序源码来源。

当前已经将源码以快照方式导入 `apps/miniapp`，导入参考提交为 `0f7b8ce`。导入时排除了：

- `.git`：旧仓库历史仍保留在 GitHub 原仓库中；
- `project.private.config.json`：微信开发者工具本地私有配置；
- 本地生成目录，例如后续可能出现的 `miniprogram_npm`。

小程序后续工作重点不是立即重写界面，而是：

- 梳理当前 `config.js` 中的旧接口；
- 将请求封装改为适配新 API 契约；
- 按身份、组织、资源、借用、项目、积分等业务域逐步改造页面；
- 能保留的页面和静态资源优先保留；
- 与新业务差异很大的流程再重做。

### 废弃小程序仓库

`mini_makers` 已明确废弃。

后续不要从该仓库复制代码，也不要把它作为问题排查来源。若发现某些功能只在该仓库出现，需要先单独确认业务价值，再决定是否重新设计。

## 分支管理

推荐分支：

| 分支 | 用途 |
| --- | --- |
| `main` | 主线分支，保持可构建、可部署、文档同步 |
| `feature/<topic>` | 功能开发分支 |
| `fix/<topic>` | 缺陷修复分支 |
| `infra/<topic>` | Docker、部署、CI/CD、运维脚本调整 |
| `docs/<topic>` | 纯文档调整 |

第一阶段可以先直接在本地提交到 `main`，但推送到 GitHub 后应逐步过渡到分支和 Pull Request。只要进入预发布或生产环境，`main` 就必须保持可追踪、可回滚。

## CI 基线

主仓库已经包含 GitHub Actions 配置：

```text
.github/workflows/ci.yml
```

当前 CI 在 push 到 `main` 和创建 Pull Request 时执行：

- 扫描 Git 已跟踪文件中的高置信度密钥；
- 安装前端依赖；
- 审计 Node 依赖，当前高危及以上漏洞会阻断；
- 构建成员网页端、后台管理端、文档站和共享包；
- 执行前端 workspace lint，其中成员网页端和后台管理端会运行 TypeScript 类型检查；
- 安装后端依赖；
- 审计 Python 依赖；
- 执行后端 ruff 检查；
- 执行后端 pytest；
- 生成 Node 和 Python CycloneDX SBOM，并作为构建产物上传；
- 构建 API、成员网页端、后台管理端和文档站 Docker 镜像，并对镜像执行可修复高危及以上漏洞扫描；
- 校验 Docker Compose 配置；
- 校验 Docker Compose YAML。

Dependabot 已配置 npm、uv、Docker 和 GitHub Actions 依赖更新。依赖更新进入 PR 后仍必须通过上述 CI。

镜像扫描采用“可修复高危及以上漏洞阻断”的策略。基础镜像中被发行版标记为 `won't fix`
的 CVE 不应让主线长期红灯，但需要在升级基础镜像、生产镜像签名和制品准入阶段持续跟踪。

后续新增数据库迁移、业务模块、前端页面和部署脚本时，应把对应检查同步加入 CI。

## 提交规则

提交信息建议使用简化的 Conventional Commits：

```text
feat: add member profile API
fix: correct points freeze calculation
docs: add repository versioning guide
infra: add docker compose healthchecks
chore: initialize makershub workspace
```

常用前缀：

| 前缀 | 含义 |
| --- | --- |
| `feat` | 新功能 |
| `fix` | 修复问题 |
| `docs` | 文档 |
| `infra` | Docker、部署、CI/CD、服务器配置 |
| `test` | 测试 |
| `refactor` | 不改变行为的代码重构 |
| `chore` | 初始化、依赖、工具和杂项 |

每个提交应尽量保持单一主题。涉及数据库、API、前端和文档的同一业务变更可以放在一个提交或一个 PR 中，但不要把无关的格式化和功能变更混在一起。

## 版本号策略

第一阶段推荐先使用仓库级版本号，而不是给每个应用单独编号。

推荐格式：

```text
v0.1.0
v0.2.0
v0.3.0
v1.0.0
```

含义：

- `v0.x.y`：正式上线前或核心能力仍在快速变化阶段；
- `v0.1.0`：基础骨架、开发环境和文档基线；
- `v0.2.0`：身份、组织、权限、积分账本基础可用；
- `v0.3.0`：资源、借用、项目基础闭环可演示；
- `v1.0.0`：第一阶段核心业务可上线、文档和运维流程完整。

补丁版本用于修复问题：

```text
v0.2.1
v0.2.2
```

只要 API、数据库、权限或部署方式发生变化，就应该在发布记录里写清楚影响范围。

## Git 标签

进入可验收阶段后，每次发布都应打 Git tag：

```bash
git tag -a v0.1.0 -m "release v0.1.0"
git push origin v0.1.0
```

tag 对应的是一个不可变的代码快照。运维排查时，生产环境应该能回答：

- 当前运行的是哪个 tag；
- 对应哪个 commit；
- 使用哪些 Docker 镜像；
- 数据库迁移执行到了哪一版。

## Docker 镜像标签

生产发布不应只依赖 `latest`。

推荐同时使用版本号和 commit hash：

```text
ghcr.io/rayflows/makershub-api:v0.1.0
ghcr.io/rayflows/makershub-api:v0.1.0-a901fb0
ghcr.io/rayflows/makershub-web:v0.1.0-a901fb0
ghcr.io/rayflows/makershub-admin:v0.1.0-a901fb0
```

也可以在未正式打 tag 前使用日期加 commit：

```text
ghcr.io/rayflows/makershub-api:20260429-a901fb0
```

原则是：

- staging 和 production 使用同一批镜像；
- staging 验证通过后推进到 production，不重新构建；
- 回滚时切回上一批镜像；
- `latest` 只用于本地开发或临时测试，不作为生产依据。

## 发布记录

每次进入 staging 或 production，都应该保留发布记录。第一阶段可以先用 Markdown 维护，后续再接入 GitHub Releases 或自动化 changelog。

建议记录字段：

| 字段 | 说明 |
| --- | --- |
| 版本号 | 例如 `v0.2.0` |
| commit | 对应 Git commit hash |
| 发布时间 | 部署到 staging 或 production 的时间 |
| 发布环境 | staging / production |
| 发布人 | 执行发布的人 |
| 镜像标签 | API、Web、Admin、Docs 对应镜像 |
| 数据库迁移 | 是否执行迁移，迁移版本号是什么 |
| 主要变更 | 用户可感知或运维需要知道的变化 |
| 验证结果 | 健康检查、核心流程、回滚检查 |
| 回滚方案 | 上一版本 tag、镜像和数据库处理方式 |

发布记录建议放在：

```text
apps/docs/docs/releases/
```

该目录可以在第一阶段后续补齐。

## 远程仓库初始化

当前本地仓库已经是 `makershub`，但 GitHub 上需要先创建空仓库：

```text
RayFlows/makershub
```

创建时建议：

- 仓库名使用 `makershub`；
- 不勾选自动创建 README；
- 不勾选自动创建 `.gitignore`；
- 不勾选自动创建 License；
- 公开或私有由项目当前公开策略决定，第一阶段可以先设为私有，稳定后再公开。

创建空仓库后，在本地执行：

```bash
git remote add origin https://github.com/RayFlows/makershub.git
git push -u origin main
```

如果本地已经存在 `origin`，则改用：

```bash
git remote set-url origin https://github.com/RayFlows/makershub.git
git push -u origin main
```

## 依赖锁定

仓库必须提交锁文件：

- 前端：`pnpm-lock.yaml`；
- 后端：`uv.lock`。

开发、CI 和 Docker 构建都应优先使用锁文件安装依赖，避免同一个 commit 在不同机器上解析出不同依赖版本。

本地更新依赖时，需要同步更新锁文件，并在提交说明中写明原因。

## 运维使用版本的方式

运维人员拿到一个生产问题时，建议先确认：

1. 当前生产环境的 Git tag 或 commit；
2. 当前运行的 Docker 镜像标签；
3. 当前数据库迁移版本；
4. 当前 `.env` 或 secret 配置版本；
5. 是否存在近期灰度、回滚或手工修复记录。

只要这些信息能对上，问题排查就可以从同一个代码快照开始。如果对不上，应优先补齐发布记录，再继续排查。
