# 权限基础设施

本目录负责权限点注册、权限判断结果和后续作用域规则。

它不负责登录认证。用户是谁、token 是否有效、会话是否被撤销，仍由 `identity` 和 HTTP 依赖处理。

## 当前已落地

- `PermissionPoint`：权限点定义；
- `PermissionRegistry`：内存权限点注册表；
- `PermissionDecision`：显式权限判断结果；
- 首批核心权限点：
  - `system.admin.access`
  - `system.audit.view`
  - `organization.member.manage`
  - `organization.department.manage`
  - `organization.position.manage`
  - `system.super_admin.recover`

## 尚未落地

- `permissions` 数据库表和迁移种子；
- 角色、用户授权和角色权限关系；
- 部门、项目、资源等作用域授权；
- FastAPI 权限依赖；
- 后台菜单权限过滤；
- 权限变更审计。

## 约束

- 业务接口不能使用 `identity_code >= 1`、`position.sort_order >= 20` 之类数字比较鉴权；
- 已注册的权限点 code 进入数据库、前端菜单和审计日志后必须保持稳定；
- `998/999` 只代表系统兜底身份，不应该自动成为所有日常业务审批角色。
