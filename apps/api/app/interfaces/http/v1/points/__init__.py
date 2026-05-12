# app/interfaces/http/v1/points/__init__.py
"""
积分与账本 V1 接口包

HTTP 层只负责认证、权限、请求响应模型和审计接入。积分余额变动规则必须留在
app.modules.points 下的 accounts、ledger、holds、adjustments 等能力模块中。
"""
