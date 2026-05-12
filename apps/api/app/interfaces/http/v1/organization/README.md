# organization

组织与成员 V1 接口目录，负责成员资料、部门列表和后续组织管理相关 HTTP 契约。

本目录负责：

- 当前用户读取和更新自己的成员资料；
- 登录后读取启用中的部门列表；
- 后台读取成员列表和成员详情；
- 后台维护成员基础资料、部门归属和普通协会职务；
- 将组织服务层结果转换为前端可消费的响应模型。

本目录不负责：

- 登录身份创建；
- 权限点授予；
- 998/999 系统底层身份指定；
- 后台批量导入导出。

## 当前接口

- `GET /api/v1/departments`：登录后查看启用中的部门；
- `GET /api/v1/positions`：查看后台可维护的普通协会职务，需要 `system.admin.access`，不返回 `998/999`；
- `GET /api/v1/me/profile`：读取当前用户成员资料；
- `PATCH /api/v1/me/profile`：当前用户自助更新成员资料；
- `GET /api/v1/members`：后台分页查看成员，需要 `organization.member.manage`；
- `GET /api/v1/members/{member_id}`：后台查看成员详情，需要 `organization.member.manage`；
- `PATCH /api/v1/members/{member_id}`：后台维护成员基础资料，需要 `organization.member.manage`，写入审计；
- `PATCH /api/v1/members/{member_id}/department`：后台调整成员当前部门，需要 `organization.department.manage`，写入审计；
- `PATCH /api/v1/members/{member_id}/positions`：后台替换成员普通协会职务，需要 `organization.position.manage`，写入审计。

## 业务边界

- 成员列表以 `users` 为根，避免微信先登录但资料未完善的用户从后台消失；
- 部门调整第一阶段采用“一个用户同一时间一个主部门”的口径，历史关系保留；
- 职务接口只维护普通协会职务，不能维护 `998/999`；
- `998/999` 的指定和恢复后续必须做成专门系统身份流程。
