# 身份认证 V1 接口

负责 `/api/v1/auth` 下的 HTTP 接口适配。

接口层只处理请求模型、响应模型、依赖注入和协议转换；具体登录、绑定、密码和权限规则下沉到 `modules/identity` 及后续权限模块。

## 已落地接口

- `POST /api/v1/auth/wechat/login`：小程序微信登录，支持本地开发态 `dev_openid`；
- `POST /api/v1/auth/refresh`：使用 refresh token 续签并轮换令牌；
- `POST /api/v1/auth/logout`：撤销 refresh token 对应的登录会话；
- `GET /api/v1/auth/me`：通过 `Authorization: Bearer <token>` 获取当前登录用户摘要。

## 后续待实现

- 邮箱验证码发送、限流和消费；
- 小程序内绑定邮箱；
- 网页端首次邮箱验证码登录；
- 首次设置密码；
- 邮箱密码登录；
- 密码重置；
- 更换绑定邮箱。
