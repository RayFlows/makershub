# v1

V1 API 路由目录，承载第一阶段正式 HTTP 契约，统一挂载到 `/api/v1`。

本目录负责：

- 汇总各业务域 V1 路由；
- 维护 auth、system、permissions、audit、organization 等接口分组；
- 保持第一阶段接口契约稳定。

本目录不负责：

- 兼容旧小程序的历史路径；
- 直接访问基础设施 SDK；
- 在路由聚合文件里写业务代码。

后续新增 V2 时，不应破坏 V1 的已发布契约；需要变更时应先更新 API 文档。

## 当前已挂载路由

总入口是 `router.py`，它只负责聚合，不写业务逻辑。

- `auth`：微信登录、邮箱登录、refresh、logout、当前用户；
- `system`：健康检查和依赖 readiness；
- `permissions`：当前用户权限摘要、权限点、角色、用户角色授权；
- `audit`：审计日志查询；
- `organization`：部门、成员资料、成员后台维护；
- `files`：上传意图和上传完成复核；
- `points`：积分账户、积分流水和受控人工调整。

请求进入某个业务路由后，应该继续进入 `modules/<domain>/service.py`。如果发现路由文件里开始堆大量业务判断，说明边界已经跑偏，需要下沉到 service。
