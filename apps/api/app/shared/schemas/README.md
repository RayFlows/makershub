# 共享 Schema

本目录用于放置跨业务域共享的 Pydantic 模型。

使用原则：

- 只放多个业务域确实共用的结构；
- 单个接口或单个业务域自己的请求/响应模型仍放在对应 `interfaces/http/v1/<domain>/schemas.py`；
- 不把业务规则写进 schema，规则应在服务层表达。
