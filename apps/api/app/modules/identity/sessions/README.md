# 登录会话能力

本目录负责 access token、refresh token 和服务端 `auth_sessions` 会话记录。

会话能力只处理“登录态是否仍然有效”和“refresh token 如何轮换/撤销”，不负责微信、
邮箱验证码或权限授予。
