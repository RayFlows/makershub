# 权限基础设施

本目录负责权限点注册、权限判断结果和后续作用域规则。

它不负责登录认证。用户是谁、token 是否有效、会话是否被撤销，仍由 `identity` 和 HTTP 依赖处理。

## 当前已落地

- `PermissionPoint`：权限点定义；
- `PermissionRegistry`：内存权限点注册表；
- `PermissionDecision`：显式权限判断结果；
- `permissions`、`roles`、`role_permissions`、`user_role_grants` ORM 模型；
- `sync_registered_permissions(...)`：权限点和系统角色幂等同步；
- `check_user_permission(...)`：统一权限判断；
- `require_permission(...)`：FastAPI 权限依赖；
- `permission.denied`：权限依赖拒绝访问时自动写入审计日志；
- `grant_user_role(...)` / `revoke_user_role_grant(...)`：可审计的业务角色授权与撤销服务；
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
  - `points.ledger.view`
  - `points.rule.view`
  - `points.rule.manage`
  - `points.temporary_rule.apply`
  - `points.temporary_rule.review`
  - `points.manual.adjust`
  - `workbench.task.publish`
- 首批核心角色：
  - `system_super_admin`：唯一 `999` 母账号，包含系统兜底权限和指定/恢复 `998` 权限；
  - `system_operator`：`998` 管理员，包含系统兜底权限；
  - `organization_manager`：维护成员资料、部门和职务；
  - `auditor`：查看审计日志；
  - `points_manager`：查看积分账户和积分流水，不包含人工调整积分能力；
  - `points_rule_applicant`：提交临时积分规则申请；
  - `points_rule_reviewer`：审批、驳回和撤回临时积分规则；
  - `points_rule_manager`：维护固定积分规则，并处理临时规则申请和审批；
- `workbench_task_publisher`：查看积分规则、发布工作台任务，并审核自己发布任务的完成结果；

## 尚未落地

- 项目、资源、场地等具体业务作用域规则；
- 后台菜单权限过滤；
- 权限拒绝告警、权限变更告警和聚合分析；
- 自定义角色创建和角色权限编辑。

## 约束

- 业务接口不能使用 `identity_code >= 1`、`position.sort_order >= 20` 之类数字比较鉴权；
- 已注册的权限点 code 进入数据库、前端菜单和审计日志后必须保持稳定；
- `998/999` 只代表系统兜底身份，默认不获得普通业务权限；
- `points.manual.adjust` 属于系统兜底权限，用于积分异常修复和受控人工调整；
- 积分规则审批和日常发放规则维护不默认落到 `998/999`，需要业务角色授权；
- `999` 额外拥有指定或恢复 `998` 的母账号动作权限；
- `998` 必须由唯一 `999` 指定；普通业务授权仍应优先授予具体业务角色。
- 普通权限写接口不能授予或撤销 `system_operator`、`system_super_admin`，它们对应的底层身份需要专门流程。
- 权限拒绝审计不记录请求体和 query string，只记录用户、权限点、路径、作用域和 request_id。
