# tests/support/__init__.py
"""
后端测试支撑工具导出

测试文件可以从这里复用临时数据库上下文、开发态登录和测试授权 helper。
业务专属 seed 仍放在各测试文件内，避免共享工具过早膨胀。
"""

from tests.support.auth import authorization_header, grant_role_to_user, login_wechat_identity, login_wechat_token
from tests.support.context import ApiTestContext, api_test_context

__all__ = [
    "ApiTestContext",
    "api_test_context",
    "authorization_header",
    "grant_role_to_user",
    "login_wechat_identity",
    "login_wechat_token",
]
