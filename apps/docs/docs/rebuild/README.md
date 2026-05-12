# MakersHub 重构文档

本目录记录 MakersHub 重构阶段的架构基线、业务分析和后续实施约定。

## 现在项目做到哪了

当前已经完成的是“后端底座 + 身份组织权限 + 积分账本基础版”：

- 单仓库多应用结构已经建立：`apps/api`、`apps/web`、`apps/admin`、`apps/docs`、`apps/miniapp`。
- 后端底座已具备：配置、数据库、迁移、统一响应、统一错误、请求 ID、日志、安全边界、健康检查。
- 身份链路已具备：微信登录、本地邮箱密码登录、短期 access token、长期 refresh token、会话撤销。
- 组织链路已具备：部门、成员资料、普通协会职务、后台成员维护。
- 权限链路已具备：权限点、角色、用户授权、`998/999` 系统兜底映射。
- 审计和文件基础已具备：审计日志、文件元数据、MinIO 上传意图。
- 积分基础已具备：积分账户、冻结记录、积分流水、幂等、受控人工调整。

还没有完成的是“完整业务闭环”：固定/临时积分规则、资源、借用、项目、小程序系统适配和后台管理端完整页面。

## 推荐阅读顺序

### 只想快速接上上下文

先读这 5 个文件：

1. [需求核对清单](./requirements-checklist.md)：业务规则以这里为准。
2. [第一阶段实施路线图](./phase-1-roadmap.md)：看当前进度和下一步。
3. [后端基础设施清单](./backend-foundation-checklist.md)：看底座是否完成、还有什么硬缺口。
4. [API 契约草案](./api-contract.md)：看接口响应、认证、权限和核心 API。
5. [后端代码注释与工程化规范](./backend-code-style.md)：看后续代码应该怎么写。
6. [后端业务域内部架构](./backend-domain-architecture.md)：看业务域内部怎么继续拆。

### 要理解为什么这么拆

继续看：

- [业务域划分](./domain-division.md)：解释为什么是 identity、organization、points、resources、borrowing、projects 这些域。
- [后端业务域内部架构](./backend-domain-architecture.md)：解释业务域下面如何继续按能力、聚合和状态机拆分。
- [数据库设计草案](./database-design.md)：看核心表和字段。
- [功能工作流](./workflows.md)：看旧系统和新系统的流程差异。

### 要做部署、Git 或本地环境

看：

- [项目结构规划](./project-structure.md)；
- [仓库与版本管理](./repository-versioning.md)；
- [环境、部署与发布周期](./environment-release-ops.md)。

## 后端代码怎么进来、怎么出去

后端启动入口：

```text
apps/api/app/main.py
```

请求入口：

```text
HTTP 请求
  -> app/main.py 注册的中间件
  -> interfaces/http/v1/router.py 总路由
  -> interfaces/http/v1/<业务域>/router.py
  -> modules/<业务域>/<能力>/service.py 或 modules/<业务域>/service.py
  -> modules/<业务域>/<能力>/repository.py 或 modules/<业务域>/repository.py
  -> modules/<业务域>/models.py
```

响应出口：

```text
成功：app/shared/responses.py 的 success_response(...)
失败：业务抛 AppError -> core/errors/handlers.py -> error_response(...)
```

登录进入：

- 小程序走 `/api/v1/auth/wechat/login`；
- 网页端和后台端走邮箱验证码首次登录或邮箱密码登录；
- 后端返回 `access_token` 和 `refresh_token`；
- 后续请求统一携带 `Authorization: Bearer <access_token>`。

登录出去：

- 客户端调用 `/api/v1/auth/logout`；
- 后端把当前 refresh session 标记为 revoked；
- 后续即使旧 access token 还没到过期时间，`/auth/me` 也会因为会话被撤销而拒绝。

## 文档语言约定

除接口路径、代码标识符、第三方技术名称和必要的英文专有名词外，项目文档默认使用中文编写。后续新增或修改文档时，也应优先使用中文，避免英文内容影响团队阅读和维护。

## 文档列表

- 项目主线：[需求核对清单](./requirements-checklist.md)、[第一阶段实施路线图](./phase-1-roadmap.md)、[后端基础设施清单](./backend-foundation-checklist.md)。
- 设计细节：[业务域划分](./domain-division.md)、[后端业务域内部架构](./backend-domain-architecture.md)、[数据库设计草案](./database-design.md)、[API 契约草案](./api-contract.md)、[功能工作流](./workflows.md)。
- 工程与运维：[项目结构规划](./project-structure.md)、[仓库与版本管理](./repository-versioning.md)、[环境、部署与发布周期](./environment-release-ops.md)、[后端代码注释与工程化规范](./backend-code-style.md)。

## 文档维护规则

新项目中的每个主要目录都应该有自己的 `README.md`，至少说明：

- 这个目录负责什么；
- 这个目录不负责什么；
- 对外暴露哪些重要契约；
- 依赖哪些其他业务域；
- 如果涉及运行维护，需要写清楚本地开发和运维说明。

长期来看，文档站应该从仓库中的 Markdown 文档生成。架构、接口、数据库、部署、运维手册和发布记录都应该跟随代码一起版本化。
