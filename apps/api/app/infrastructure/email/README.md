# 邮件基础设施适配

负责验证码、系统通知等邮件发送通道适配。

当前优先支持本地开发的 `log` 模式，验证码会写入服务日志；后续配置 SMTP 后切换为真实邮件发送。

第一阶段真实验证码发信服务暂定使用 Resend，项目域名记录为 `scumaker.com`。Resend 验证域名后，
可以直接从该域名下任意地址发信，不需要额外创建邮箱账号；验证码推荐发件人：

```env
EMAIL_DELIVERY_MODE=smtp
SMTP_HOST=smtp.resend.com
SMTP_PORT=465
SMTP_USE_SSL=true
SMTP_USERNAME=resend
SMTP_PASSWORD=<RESEND_API_KEY>
SMTP_FROM_EMAIL=auth@scumaker.com
SMTP_FROM_NAME=MakersHub
```

`SMTP_PASSWORD` 必须通过本地 `.env`、部署平台 secret 或服务器环境变量注入，不能提交真实值。

本目录只负责技术发送，不决定验证码有效期、频率限制、绑定邮箱等业务规则。
