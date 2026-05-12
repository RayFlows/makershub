# 权限接口

本目录放 `/api/v1/permissions` 相关接口。

## 当前能力

- `GET /permissions/me`：当前用户权限摘要；
- `GET /permissions`：查看系统权限点，需要 `system.admin.access`；
- `GET /permissions/roles`：查看角色与权限关系，需要 `system.permission.manage`。
- `GET /permissions/users/{user_id}/roles`：查看用户角色授权记录，需要 `system.permission.manage`；
- `POST /permissions/users/{user_id}/roles`：给用户授予业务角色，需要 `system.permission.manage`，写入 `permission.user_role_grant.create` 审计；
- `POST /permissions/role-grants/{user_role_grant_id}/revoke`：撤销用户角色授权，需要 `system.permission.manage`，写入 `permission.user_role_grant.revoke` 审计。

## 重要边界

- 普通授权接口只处理可审计的业务角色，例如组织管理人员、审计查看员；
- `system_operator` 和 `system_super_admin` 不能通过这些接口授予或撤销；
- `998/999` 是底层系统职务，不是日常业务角色，必须走专门的 999 指定或运维初始化流程；
- 第一阶段授权作用域只开放 `global` 和 `department`，项目、资源、场地等作用域等对应业务域落地后再开放。

## 暂未开放

- 创建或修改角色；
- 按项目、资源、场地等作用域管理授权；
- 权限变更告警和聚合分析；
- 后台菜单过滤接口。
