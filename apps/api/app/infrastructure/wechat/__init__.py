# app/infrastructure/wechat/__init__.py
"""
微信基础设施适配导出

微信 code2session 属于外部服务调用，放在 infrastructure 层。
身份域只消费 openid/unionid/session_key 等结果，不直接拼微信 API 地址。
"""

from app.infrastructure.wechat.client import WechatSession, exchange_code_for_session

__all__ = ["WechatSession", "exchange_code_for_session"]
