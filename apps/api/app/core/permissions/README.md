# 权限基础设施

本目录负责权限点注册、权限判断结果和后续作用域规则。

它不负责登录认证。用户是谁、token 是否有效、会话是否被撤销，仍由 `identity` 和 HTTP 依赖处理。

## 当前已落地

- `PermissionPoint`：权限点定义；
- `PermissionRegistry`：内存权限点注册表；
- `PermissionDecision`：显式权限判断结果；
- `permissions`、`roles`、`role_permissions`、`user_roles` ORM 模型；
- `sync_registered_permissions(...)`：权限点和系统角色幂等同步；
- `check_user_permission(...)`：统一权限判断；
- `require_permission(...)`：FastAPI 权限依赖；
- 首批核心权限点：
  - `system.admin.access`
  - `system.audit.view`
  - `system.permission.manage`
  - `organization.member.manage`
  - `organization.department.manage`
  - `organization.position.manage`
  - `system.super_admin.recover`
  - `files.upload`
  - `files.manage`

## 尚未落地

- 权限变更写接口；
- 部门、项目、资源等具体业务作用域规则；
- 后台菜单权限过滤；
- 权限变更审计。

## 约束

- 业务接口不能使用 `identity_code >= 1`、`position.sort_order >= 20` 之类数字比较鉴权；
- 已注册的权限点 code 进入数据库、前端菜单和审计日志后必须保持稳定；
- `998/999` 只代表系统兜底身份，底层能力一致；
- `998` 必须由唯一 `999` 指定；普通业务授权仍应优先授予具体业务角色。
