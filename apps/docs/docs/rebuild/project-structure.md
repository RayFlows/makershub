# MakersHub 项目结构规划

## 目标

本文档记录 `makershub` 的目标目录结构。它用于指导后续创建新仓库骨架，避免继续沿用旧项目中按 `models`、`routes`、`services` 三层平铺的结构。

新系统采用单仓库多应用结构：后端、成员网页端、后台管理端、文档站和小程序源码放在同一个仓库中，前端共享包统一放在 `packages/` 下。

## 顶层结构

```text
makershub/
  apps/                         # 所有可以独立运行的应用
    api/                        # FastAPI 后端服务
    web/                        # 成员网页端，第一阶段优先实现
    admin/                      # 新后台管理系统，直接重写，不迁移旧后台 UI
    docs/                       # VitePress 文档站
    miniapp/                    # 小程序源码，从原 MakersHub_Front-end 导入

  packages/                     # 多个前端应用共享的代码
    api-client/                 # 共享 API 客户端和接口类型
    ui/                         # 共享 UI 组件、主题、表单封装
    config/                     # 共享前端工程配置

  infra/                        # 部署和基础设施配置
    docker/                     # Dockerfile、compose、镜像构建相关
    nginx/                      # Nginx 配置
    mysql/                      # MySQL 初始化、备份、恢复相关
    minio/                      # MinIO 初始化桶、策略等

  .github/
    workflows/                  # GitHub Actions CI/CD 配置

  scripts/                      # 开发、初始化、运维脚本
  README.md                     # 项目总说明
  pnpm-workspace.yaml           # 前端工作区配置
  pyproject.toml                # Python 后端依赖和工具配置
```

## 应用目录说明

### `apps/api`

`apps/api` 是 FastAPI 后端服务，保留旧项目已经验证过的后端技术方向，但按业务域重新组织代码。

```text
apps/api/
  app/
    core/                       # 后端核心能力
      config/                   # 配置读取、环境变量、运行模式
      database/                 # SQLAlchemy 异步连接、事务、会话管理
      errors/                   # 应用异常和统一错误处理
      security/                 # 密码、令牌、签名、安全工具
      permissions/              # 权限点注册、权限检查、作用域规则
      logging/                  # 日志配置和日志上下文

    shared/                     # 后端通用工具
      schemas/                  # 公共请求/响应结构
      pagination.py             # 分页参数和分页响应
      responses.py              # 统一响应格式
      request_context.py        # 请求 ID 和请求上下文
      ids/                      # 业务编号、雪花 ID 或短 ID 生成
      time/                     # 时间处理工具

    modules/                    # 业务域模块
      identity/                 # 身份与登录
      organization/             # 组织与成员
      points/                   # 积分与账本
      resources/                # 资源、物资、场地、工位
      borrowing/                # 借用、预约、归还、异常处理
      projects/                 # 项目立项、材料、结项、中断、风控
      workbench/                # 任务、悬赏、排班、值班
      content/                  # 活动、公告、秀米链接，后续博客
      notifications/            # 微信订阅消息、邮件、站内通知
      audit/                    # 审计日志、审批轨迹、安全事件

    infrastructure/             # 外部基础设施适配
      mysql/                    # MySQL 方言、仓储基础实现
      minio/                    # 文件上传、访问链接、桶策略
      wechat/                   # 微信登录、订阅消息接口

    interfaces/                 # 对外接口层
      http/
        v1/                     # 正式 V1 API 路由

  migrations/                   # 数据库迁移脚本
    env.py                      # Alembic 迁移环境配置
    versions/                   # Alembic 迁移版本
  tests/                        # 后端测试
```

每个业务域模块默认包含：

```text
modules/<业务域>/
  README.md                     # 说明该业务域负责什么、不负责什么
  models.py                     # 数据模型
  schemas.py                    # 请求和响应结构
  repository.py                 # 数据库访问
  service.py                    # 业务逻辑
  permissions.py                # 权限点和作用域规则
  router.py                     # HTTP 接口
  events.py                     # 领域事件
```

当业务域变大时，可以继续拆子目录，例如：

```text
modules/borrowing/
  README.md
  applications/                 # 借用申请
  reviews/                      # 审核
  returns/                      # 归还
  conflicts/                    # 冲突检测
```

### `apps/web`

`apps/web` 是成员网页端，第一阶段优先实现，用来验证核心业务逻辑。

它主要承接：

- 邮箱验证码登录和首次设置密码；
- 个人资料和邮箱绑定；
- 积分余额、冻结积分和积分流水查看；
- 物资、场地、工位浏览；
- 借用申请、取消、归还状态查看；
- 项目立项、材料上传、结项提交；
- 后续任务、值班、临时积分规则相关成员操作。

网页端能力包含且大于小程序端。较长表单、文件上传、反复修改的申请优先放在网页端跑通，再逐步接入小程序。

### `apps/admin`

`apps/admin` 是新后台管理系统，直接重写，不迁移旧后台前端。

它主要承接：

- 成员和组织管理；
- 权限和角色管理；
- 物资、场地、工位管理；
- 借用审核、异常归还、损耗处理；
- 项目审核、项目中断、项目风控；
- 积分规则、临时积分规则、积分流水查看；
- 导出、审计、系统配置和运维兜底操作。

后台访问不等于 `998/999`。业务人员可以进入自己有权限的后台模块，`998/999` 只负责底层系统兜底、敏感配置和异常修复。

### `apps/docs`

`apps/docs` 是 VitePress 文档站。

它用于维护：

- 架构说明；
- 业务域说明；
- 权限模型；
- API 契约；
- 数据库模型；
- 本地开发说明；
- 测试、预发布、生产和灾备运维手册；
- 发布记录；
- 故障记录。

项目文档默认使用中文。每次需求、结构或实现策略发生变化，都需要同步更新文档。

### `apps/miniapp`

`apps/miniapp` 是小程序源码目录，已经从原 `RayFlows/MakersHub_Front-end` 导入。

微信开发者工具可以直接打开 `apps/miniapp` 子目录，不需要打开整个 `makershub` 根目录。因此小程序放在单仓库中不会天然增加本地开发难度。

第一阶段先用网页端验证业务逻辑。小程序后续接入时，重点改造 API 层和数据适配层，页面能保留的优先保留。原 `mini_makers` 仓库不作为迁移来源。

## 共享包说明

### `packages/api-client`

`packages/api-client` 保存前端共享 API 客户端和接口类型。

目标是让 `apps/web`、`apps/admin` 和后续 `apps/miniapp` 尽量调用同一套接口契约，避免网页端、小程序端和后台管理端出现三套数据结构。

### `packages/ui`

`packages/ui` 保存网页端和后台管理端共享的 UI 组件。

第一阶段建议使用 React、Vite、TypeScript 和 Ant Design Pro 风格。旧后台的 React 和 Ant Design 经验可以保留，但不继续使用旧的 CRA/react-scripts 工程结构。

### `packages/config`

`packages/config` 保存共享前端工程配置，例如：

- TypeScript 配置；
- ESLint 配置；
- Vite 基础配置；
- 路径别名约定；
- 前端代码风格约定。

## 第一阶段建设顺序

当前单仓库骨架、Docker 开发环境、GitHub CI 基线和后端基础设施已经创建完成。后续建设顺序如下：

1. 在 `apps/api` 中优先实现身份、组织、权限、积分账本基础。
2. 在 `apps/web` 中跑通登录、资料、借用、项目、积分流水。
3. 在 `apps/admin` 中按业务域逐步补管理和审核能力。
4. 持续维护 `apps/docs`，把开发文档和运维文档纳入版本管理。
5. 等网页端和 API 契约稳定后，再接入 `apps/miniapp`。

## 第一阶段暂不深入

以下能力第一阶段只保留边界或占位，不阻塞核心闭环：

- 3D 打印和服务器借用的具体申请字段；
- 项目招募完整流程；
- 博客；
- 社区；
- 电控；
- AI；
- NFC、WiFi 在线时长、视觉检测等硬件联动；
- 完整积分经济模型和积分等级称号。
