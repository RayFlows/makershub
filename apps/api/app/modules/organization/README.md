# 组织与成员

负责部门、成员资料、协会身份、职务身份、成员状态和花名册。

不负责登录凭证、积分账本和具体业务审批。

## 已落地的基础能力

当前已落地第一阶段组织底座：

- `departments`：协会部门定义，首批包含宣传部、基管部、项目部、运维部；
- `member_profiles`：成员资料，承接旧小程序里的真实姓名、手机号、学号、联系邮箱、QQ、学院、专业、年级等字段；联系邮箱默认来自登录邮箱，但允许成员修改，后端只校验邮箱格式，不发送验证码；
- `department_memberships`：部门成员关系，记录成员当前和历史部门归属；
- `positions`：身份和职务定义，首批种子包含外部成员 `0`、干事、部长、副会长、会长、指导老师、`998`、`999`；
- `user_positions`：用户职务关系，用于表达 `999` 等系统身份和普通协会职务。

当前 HTTP 接口已开放：

- 当前登录用户自己的资料读取和更新；
- 登录后读取部门列表；
- 后台读取成员列表和成员详情；
- 后台维护成员资料、部门归属和普通协会职务。

## 当前入口

组织域已经拆成二级能力模块。根目录不再保留 `service.py` 和 `repository.py`，调用方应按
业务意图导入明确入口：

| 能力 | 导入入口 | 典型调用方 |
| --- | --- | --- |
| 成员资料、自助资料、后台成员列表和详情 | `app.modules.organization.members` | 组织 HTTP 路由 |
| 部门列表和成员部门调整 | `app.modules.organization.departments` | 组织 HTTP 路由、成员聚合 |
| 职务列表和成员职务替换 | `app.modules.organization.positions` | 组织 HTTP 路由、成员聚合 |
| 聚合返回对象和值校验 | `app.modules.organization.types`、`app.modules.organization.utils` | 组织域内部能力和测试 |

## 目录结构

```text
organization/
  models.py                     # 部门、成员资料、部门关系、职务关系模型
  types.py                      # 服务层聚合返回结构
  utils.py                      # 成员资料、用户字段和职务 code 校验
  members/
    README.md
    service.py                  # 自助资料、后台成员列表、成员详情和资料维护
    repository.py               # users/member_profiles 查询和写入
  departments/
    README.md
    service.py                  # 部门列表和成员部门调整
    repository.py               # departments/department_memberships 查询和写入
  positions/
    README.md
    service.py                  # 普通职务列表和成员职务替换
    repository.py               # positions/user_positions 查询和写入
```

## 领域边界

- 登录身份、微信 openid、邮箱密码和登录会话属于 `identity`，不写在组织域；
- 部门归属、职务身份和成员资料属于组织域；
- `0` 是外部成员/协会会员的基础身份，不是权限点，也不会自动授予后台管理能力；
- 积分余额和积分流水后续进入积分账本域，组织域最多读取展示，不直接改余额；
- 后台调整他人资料、部门和职务必须接入权限点和审计，不能复用个人资料自助接口；
- 职务接口只维护普通协会职务，不能维护 `998/999`，后者必须走系统身份专门流程。
- 不要恢复根目录 `service.py` 或 `repository.py`；新增组织能力继续拆到二级能力模块。

## 旧代码差异

旧 `makershub-backend` 的 `users` 表同时保存 `userid/openid`、`real_name`、`phone_num`、
`department`、`score` 等字段。新实现保留字段语义，但拆成多个业务域：

- `users` 只表示内部用户主体；
- `wechat_accounts` 保存微信登录凭证；
- `member_profiles.phone` 对应旧接口里的 `phone_num`；
- `department_memberships` 替代旧的单个数字 `department`；
- 积分后续由账本系统负责，不再放在用户或成员资料表里。
