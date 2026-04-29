# 微信基础设施适配

负责微信小程序外部接口适配，例如 `code2session`。

本目录只负责技术调用和错误转换，不负责创建用户主体、签发 MakersHub 访问令牌，也不决定登录业务流程。身份业务规则应放在 `modules/identity`。

## 已落地能力

- `exchange_code_for_session`：调用微信 `jscode2session`，把小程序临时 `code` 换成 `openid`、`unionid` 和 `session_key`。

## 后续待实现

- 微信订阅消息发送适配；
- 微信接口调用限流、重试和结构化日志；
- 更细的微信错误码映射。
