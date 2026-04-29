# tests/test_tokens.py
"""
访问令牌测试

令牌过期需要有独立错误码，方便小程序和网页端准确清理认证缓存并重新登录。
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from app.core.errors import AppError
from app.core.security import decode_access_token, issue_access_token


def test_decode_access_token_reports_expired_token() -> None:
    """过期令牌应返回稳定的 ACCESS_TOKEN_EXPIRED 错误码。"""

    token = issue_access_token(subject=1, expires_delta=timedelta(minutes=-1)).token

    with pytest.raises(AppError) as exc_info:
        decode_access_token(token)

    assert exc_info.value.code == "ACCESS_TOKEN_EXPIRED"
    assert exc_info.value.status_code == 401


def test_issue_access_token_returns_client_expiry_metadata() -> None:
    """签发令牌时应同时返回客户端可缓存的过期信息。"""

    token = issue_access_token(
        subject=1,
        extra_claims={"channel": "wechat"},
        expires_delta=timedelta(minutes=5),
    )

    claims = decode_access_token(token.token)
    assert token.expires_in > 0
    assert claims["sub"] == "1"
    assert claims["channel"] == "wechat"
