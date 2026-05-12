# 身份域仓储拆分

本目录保存身份域内部仓储能力。

仓储层只封装数据库查询和写入，不决定业务流程是否允许执行，也不提交事务。业务规则由
`accounts`、`email_codes`、`sessions`、`bootstrap` 等服务模块负责。

当前拆分：

- `base.py`：用户主体、最近登录时间、职务查询等共享能力；
- `accounts.py`：微信账号和邮箱密码账号读写；
- `email_codes.py`：邮箱验证码记录读写；
- `sessions.py`：登录会话读写；
- `__init__.py`：组合 `IdentityRepository` 仓储入口。

外部模块如确实需要读取用户主体，可以通过
`app.modules.identity.repositories.IdentityRepository` 导入统一仓储入口；不要直接导入本目录
内部 mixin。
