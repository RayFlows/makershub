# 后端业务域内部架构

## 目标

本文档规定 `apps/api/app/modules` 下业务域的内部拆分方式。

重构的目的不是把旧代码按 `identity`、`points`、`borrowing` 等名字重新装进几个大文件里，
而是让系统在业务继续增长时仍然能被理解、测试、替换和交接。只做到“按业务域分目录”
是不够的；业务域内部还必须继续按能力、聚合和状态机拆分。

## 为什么业务域还要继续拆

旧系统的问题不是单纯目录名不好，而是多种业务事实、入口适配、权限判断、数据写入和临时
补丁混在一起。新系统如果只把它们搬到 `modules/<domain>/service.py`，最后仍然会变成：

- 一个文件同时处理十几条业务链路；
- 一个 Repository 承担所有查询和写入；
- 业务规则只能靠全文搜索查找；
- 新人不敢改，AI 也容易在上下文压缩后忘记约束；
- 后续资源、借用、项目、积分规则一接入，又要二次重构。

因此业务域目录只是第一层边界。真正可维护的结构应该继续拆到“单个能力或单个状态机”
这个粒度。

## 基本分层

后端业务代码按以下层次组织：

```text
interfaces/http/v1/<domain>/     # HTTP 契约层，负责请求、响应、鉴权依赖和审计入口
modules/<domain>/                # 业务域层，负责业务事实和业务规则
modules/<domain>/<capability>/   # 域内能力模块，负责一个清晰业务链路
core/                            # 跨业务域技术底座
infrastructure/                  # 外部系统适配
shared/                          # 无业务归属的通用工具
```

HTTP 路由不放回业务域。小程序、成员网页端和后台管理端都应该通过 `interfaces` 进入系统；
业务域暴露稳定服务函数或门面函数给接口层调用。

## 业务域内部标准结构

一个仍然较小的业务域可以临时保持扁平：

```text
modules/<domain>/
  README.md
  __init__.py
  models.py
  repository.py
  service.py
```

一旦业务域变大，必须拆成下面这种形态：

```text
modules/<domain>/
  README.md                      # 业务域总边界
  __init__.py
  models.py 或 models/           # 该域拥有的数据库事实
  events.py                      # 该域对外发布的领域事件
  types.py                       # 该域共享值对象和返回结构
  policies.py                    # 该域共享业务策略，避免散落在接口层

  <capability>/
    README.md                    # 该能力负责什么、不负责什么
    service.py                   # 该能力的业务用例
    repository.py                # 该能力需要的查询和写入
    types.py                     # 该能力内部 DTO/结果类型，可选
```

`models.py` 是否继续单文件，取决于模型规模。模型少时可以保留单文件；当一个域出现多个
聚合根或模型超过 300 行时，应该拆成 `models/` 包。

## 拆分触发条件

满足任一条件，就不应继续往单个 `service.py` 或 `repository.py` 里加代码：

- 单个 `service.py` 超过 350 行；
- 单个 `repository.py` 超过 300 行；
- 一个文件同时处理 3 条以上独立业务链路；
- 一个业务域拥有 2 个以上聚合根；
- 一个业务链路有独立状态机，例如借用申请、项目审核、积分规则审批；
- 一个业务链路同时服务成员端和后台端，但权限、审计、字段差异明显；
- 新增代码需要频繁修改同一个大文件的多个分区。

这些阈值不是为了追求小文件，而是为了防止业务规则被淹没。

## 模块依赖规则

依赖方向必须保持单向：

```text
interfaces -> modules -> repository/models
modules -> core/shared/infrastructure
```

跨业务域调用必须走对方公开服务或门面函数，不能直接写对方 Repository 或表。例如：

- `borrowing` 冻结押金时，只能调用 `points` 暴露的冻结服务；
- `organization` 可以展示积分余额，但不能直接更新 `point_accounts`；
- `resources` 负责资源主数据，不能直接决定借用审批结果；
- `identity` 负责用户主体和登录凭证，不能直接授予业务审批权限。

事务边界仍由接口层或明确的应用用例控制。Repository 不提交事务，避免隐藏副作用。

## 当前已落地域的拆分目标

### `identity`

`identity` 已按能力完成第一轮拆分，并且不再保留旧的 `service.py`、`repository.py`
根目录入口。接口层和其他业务域需要直接依赖明确的二级能力入口。

当前结构：

```text
modules/identity/
  models.py
  types.py
  utils.py
  accounts/
    email_password.py            # 邮箱密码账号绑定、首次登录、设置密码、密码登录
    wechat.py                    # 微信 openid/unionid 登录身份
  sessions/
    service.py                   # access/refresh token、会话轮换、撤销
  email_codes/
    service.py                   # 验证码签发、限流、消费
  bootstrap/
    service.py                   # 唯一 999 初始化
  repositories/
    accounts.py                  # 微信账号和邮箱密码账号数据库操作
    email_codes.py               # 验证码数据库操作
    sessions.py                  # 登录会话数据库操作
    base.py                      # 用户主体和职务查询等共享仓储能力
```

后续不得再恢复单文件 `identity/service.py`。新增身份能力必须进入对应二级能力模块；
如果需要跨能力编排，应新建明确的应用用例模块，而不是重新堆回域根目录。

### `organization`

组织域已经按成员资料、部门关系和职务关系完成第一轮拆分，并且不再保留旧的
`service.py`、`repository.py` 根目录入口。组织域只处理成员资料和组织关系，不处理
登录凭证、积分账本和具体业务审批。

当前结构：

```text
modules/organization/
  models.py
  types.py
  utils.py
  members/                       # 成员资料、自助资料、后台成员维护
    service.py
    repository.py
  departments/                   # 部门主数据和部门成员关系
    service.py
    repository.py
  positions/                     # 0-5 普通职务，不维护 998/999
    service.py
    repository.py
```

后续花名册、部门履历、系统身份恢复等能力继续按二级模块新增；998/999 的系统身份
维护不能混入普通成员职务接口。

### `points`

积分是账本系统，已经按账本事实完成第一轮拆分，并且不再保留旧的
`service.py`、`repository.py` 根目录入口。后续借用、任务、项目等业务域只能调用
明确能力模块，不能直接修改余额。

当前结构：

```text
modules/points/
  models.py
  constants.py
  types.py
  utils.py
  accounts/                      # 积分账户读取和懒创建
    service.py
    repository.py
  ledger/                        # 流水追加、查询、幂等结果恢复
    service.py
    repository.py
  holds/                         # 冻结、解冻、冻结转扣除
    service.py
    repository.py
  adjustments/                   # 受控人工调整
    service.py
```

后续 `rules`、异常追回、积分通知等能力继续按二级模块新增，不得恢复根目录大文件。

## 待落地域的拆分目标

### `resources`

```text
modules/resources/
  catalog/                       # 资源分类、资源主数据
  inventory/                     # 库存、资产数量、可借状态
  locations/                     # 场地、工位、空间结构
  maintenance/                   # 维护中、下架、损坏状态
```

### `borrowing`

```text
modules/borrowing/
  applications/                  # 借用申请
  reviews/                       # 审核和审批意见
  schedules/                     # 预约时段和冲突检测
  returns/                       # 归还、验收、解冻押金
  exceptions/                    # 逾期、损坏、丢失、扣分
```

### `projects`

```text
modules/projects/
  applications/                  # 项目立项申请
  members/                       # 项目成员和角色
  materials/                     # 立项材料、结项材料、附件
  reviews/                       # 审核、退回、通过
  lifecycle/                     # 中断、结项、归档、风控
```

### `workbench`

```text
modules/workbench/
  tasks/                         # 日常任务、临时任务
  schedules/                     # 排班和值班
  duty/                          # 值班申请和值班记录
  cleaning/                      # 打扫卫生、大扫除记录
```

### `content`

```text
modules/content/
  activities/                    # 活动、报名、活动归档
  announcements/                 # 公告
  publicity_links/               # 宣传链接、秀米链接和审核
  posts/                         # 后续官方博客或内容文章
```

## 当前整改顺序

为了避免在基础还未稳定时大范围移动文件，拆分按以下顺序增量推进：

1. 先把本文档作为后续模块建设硬约束；
2. 新增业务域时直接按二级能力模块创建，不再先写一个大 `service.py`；
3. 优先拆 `identity`，因为它已经承担多条认证链路；
4. 再拆 `points`，把账户、冻结、流水、人工调整分开；
5. 再拆 `organization`，把成员、部门、职务分开；
6. 后续实现 `resources`、`borrowing`、`projects` 时直接按上面的目标结构落地。

临时保留扁平结构时，必须在该域 README 中写清楚“这是第一阶段临时结构”和计划拆分方向。
