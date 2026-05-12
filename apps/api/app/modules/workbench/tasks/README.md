# 工作台任务能力

本目录负责工作台里的任务闭环：发布、领取、提交完成材料、发布人审核，以及审核通过后
按积分规则发放积分。

## 负责什么

- 发布指定任务和悬赏任务；
- 悬赏任务领取后直接进入待完成；
- 执行人提交完成材料后进入待审核；
- 发布人审核通过或打回；
- 审核通过后调用积分域 `grant_points_by_rule(...)` 发放积分；
- 任务状态和积分流水保留可追溯关系。

## 目录结构

- `service.py`：任务主状态机，描述发布、领取、提交和审核的业务流转；
- `repository.py`：任务表读写，不提交事务；
- `validators.py`：任务字段枚举、领取范围和部门范围校验；
- `README.md`：任务能力边界和状态流转说明。

## 不负责什么

- 不维护积分规则本身，规则由 `points.rules` 管理；
- 不处理排班和值班报名，这些后续进入 `schedules` / `duty` 能力；
- 不做通知触达，临时规则撤回后的用户通知后续由通知域接入；
- 不直接修改积分账户余额。

## 状态流转

```text
指定任务:
pending_completion -> pending_review -> completed
pending_completion -> pending_review -> rejected -> pending_review

悬赏任务:
pending_claim -> pending_completion -> pending_review -> completed

异常:
pending_review -> rule_revoked_pending
```

说明：

- `rejected` 表示发布人打回完成材料，执行人可以重新提交；
- `rule_revoked_pending` 表示任务引用的积分规则已撤回，不能自动发分；
- 已完成任务不再通过任务接口撤回积分，异常追回必须走积分域反向流水。
