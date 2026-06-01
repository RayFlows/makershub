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
EMAIL_HOME_URL=https://scumaker.com
EMAIL_BRAND_IMAGE_URL=https://static.scumaker.com/public/brand/SCUMAKER_logowithtext_email.png
```

`SMTP_PASSWORD` 必须通过本地 `.env`、部署平台 secret 或服务器环境变量注入，不能提交真实值。

本目录只负责技术发送，不决定验证码有效期、频率限制、绑定邮箱等业务规则。

验证码邮件使用 HTML + 纯文本双版本。

- HTML 版本优先使用 `EMAIL_BRAND_IMAGE_URL` 指向的公开品牌图，图片点击后跳转到 `EMAIL_HOME_URL`；
- 品牌图应放在 MinIO public bucket 或等价公开静态资源服务中，不能使用 CID 附件图片；
- 邮件品牌图使用从原始透明 PNG 生成的浅底版本，避免 QQ 邮箱等客户端在夜间模式下把透明区域渲染成黑底；
- 纯文本版本用于不显示 HTML 或拦截图片的邮件客户端；
- 邮件模板只展示用途、验证码、有效期和安全提示，不放置未接入的跳转按钮。

本地开发已经把 `SCUMAKER_logowithtext_email.png` 放在 `makershub-public-local`：

```env
EMAIL_BRAND_IMAGE_URL=http://localhost:9000/makershub-public-local/brand/SCUMAKER_logowithtext_email.png
```

真实发给外部邮箱时必须换成公网 HTTPS 地址，例如：

```env
EMAIL_BRAND_IMAGE_URL=https://static.scumaker.com/public/brand/SCUMAKER_logowithtext_email.png
```

## 发件人头像

邮件列表或邮件详情中的“发件人头像”不是邮件 HTML 模板控制的内容。它通常由收件人邮箱客户端根据以下来源自行决定：

- 收件人本地通讯录头像；
- 邮箱客户端自己的品牌识别规则；
- 域名层面的 BIMI/DNS 品牌记录；
- 发件平台账号资料，但这不一定会同步给所有收件邮箱。

因此，`SMTP_FROM_NAME`、正文 logo 或 `EMAIL_BRAND_IMAGE_URL` 只能影响邮件内容和发件人展示名，不能保证改变
QQ 邮箱、学校邮箱或 Gmail 等客户端里的发件人头像。后续如果要做域名级品牌头像，应单独规划 BIMI 记录、
DMARC 策略和适合邮箱客户端使用的方形品牌图。
