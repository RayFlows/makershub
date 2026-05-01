# 权限接口

本目录放 `/api/v1/permissions` 相关接口。

## 当前能力

- `GET /permissions/me`：当前用户权限摘要；
- `GET /permissions`：查看系统权限点，需要 `system.admin.access`；
- `GET /permissions/roles`：查看角色与权限关系，需要 `system.permission.manage`。

## 暂未开放

- 创建或修改角色；
- 给用户授予角色；
- 撤销用户角色；
- 按部门、项目、资源等作用域管理授权。

这些写接口必须先接入审计日志，避免权限变更只留在运行日志里。
