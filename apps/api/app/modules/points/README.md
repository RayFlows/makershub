# 积分与账本

积分域负责积分账户、冻结余额、积分流水和受控人工调整。积分在 MakersHub 中相当于
协会内部货币，不能再像旧后端一样放在 `users.score` 上被成员资料接口直接覆盖。

其他业务域如果需要发放、扣减、冻结或解冻积分，必须调用本域公开能力，不能直接更新
`point_accounts`，也不能把积分重新塞回 `users` 或成员资料表。

## 关键业务约束

- 每个用户都应有积分账户，外部成员 `0` 也有积分账户；
- 积分变动必须追加流水；
- 不允许业务代码直接修改余额；
- 同一业务事件必须通过 `idempotency_key` 保持幂等；
- 不允许积分透支；
- 不允许用户之间转账；
- 冻结余额不是扣除积分，只是暂时锁住可用余额；
- 正常归还或取消后解冻，逾期、损坏、丢失或确认消耗时才允许冻结转扣除；
- 撤回、追回和异常修正必须通过反向流水表达，不能删除或覆盖旧流水；
- 人工调整必须填写原因，并由接口层或应用用例层写审计日志。

## 当前入口

根目录不再保留 `service.py` 和 `repository.py`，调用方应按业务意图导入明确入口：

| 能力 | 导入入口 | 典型调用方 |
| --- | --- | --- |
| 积分账户读取和懒创建 | `app.modules.points.accounts` | 成员端、后台账本查询、其他积分能力 |
| 积分流水查询和幂等恢复 | `app.modules.points.ledger` | 成员端、后台账本查询、积分域内部 |
| 冻结、解冻、冻结转扣除 | `app.modules.points.holds` | 后续借用、打印、资源占用等业务域 |
| 受控人工补发和扣减 | `app.modules.points.adjustments` | 后台人工调整接口 |
| 结果对象和值校验 | `app.modules.points.types`、`app.modules.points.utils` | 积分域内部能力和测试 |

## 目录结构

```text
points/
  models.py                     # 积分账户、冻结记录和流水模型
  constants.py                  # 账户状态、冻结状态和流水方向
  types.py                      # 服务层返回结构
  utils.py                      # 金额、原因、业务标签和幂等键校验
  accounts/
    README.md
    service.py                  # 积分账户读取和懒创建
    repository.py               # point_accounts 查询和创建
  ledger/
    README.md
    service.py                  # 流水查询、追加余额快照和幂等结果恢复
    repository.py               # point_ledger_entries 查询和写入
  holds/
    README.md
    service.py                  # 冻结、解冻和冻结转扣除
    repository.py               # point_holds 查询和写入
  adjustments/
    README.md
    service.py                  # 受控人工补发和扣减
```

## 已落地能力

- `PointAccount`：每个用户一个积分账户，保存 `balance` 和 `frozen_balance`；
- `PointHold`：保存借用押金、3D 打印接单等业务冻结生命周期；
- `PointLedgerEntry`：保存所有积分变动事实和余额快照；
- `manually_adjust_points(...)`：`998/999` 系统兜底使用的人工补发或扣减；
- `freeze_points(...)`：冻结可用积分，不改变总余额；
- `release_point_hold(...)`：解冻有效冻结记录；
- `deduct_point_hold(...)`：把冻结记录转为实际扣除；
- `idempotency_key`：防止同一业务事件重复发放、重复冻结或重复扣除。

## 调用链路

查看当前用户积分账户：

```text
/api/v1/me/points/account
  -> points.accounts.get_or_create_point_account
  -> point_accounts
```

查看积分流水：

```text
/api/v1/me/points/ledger 或 /api/v1/points/ledger
  -> points.ledger.list_point_ledger_entries
  -> point_ledger_entries
```

后台人工调整：

```text
/api/v1/points/manual-adjustments
  -> require_permission("points.manual.adjust")
  -> points.adjustments.manually_adjust_points
  -> point_accounts + point_ledger_entries
  -> audit_logs
```

后续借用押金冻结：

```text
borrowing 应用用例
  -> points.holds.freeze_points
  -> point_holds + point_ledger_entries

归还/异常处理
  -> points.holds.release_point_hold 或 points.holds.deduct_point_hold
  -> point_holds + point_ledger_entries
```

## 不负责什么

- 不负责登录认证，当前用户由 HTTP 依赖提供；
- 不负责权限判断，后台接口通过 `require_permission(...)` 检查权限；
- 不负责日常积分规则审批，固定规则和临时规则会在后续业务接口中单独实现；
- 不负责小程序旧 `score` 字段兼容，后续由接口适配层或小程序 API 客户端迁移。

## 维护约束

- 不要恢复根目录 `service.py` 或 `repository.py`；
- 余额缓存只能由积分域服务层维护；
- 积分不允许透支；
- 积分变动必须追加流水；
- 仓储层不提交事务，只封装查询和写入；
- 人工调整必须填写原因，并由接口层写入审计日志；
- 撤回、追回和异常修正必须通过反向流水表达，不能删除或覆盖旧流水；
- 运行日志、审计日志和积分流水是三类不同信息，不能互相替代。

## 后续待实现

- 固定积分规则；
- 临时积分规则申请、审批、撤回；
- 一次性任务模板和积分发放；
- 异常追回和反向流水修正用例；
- 积分通知和受影响用户提醒。
