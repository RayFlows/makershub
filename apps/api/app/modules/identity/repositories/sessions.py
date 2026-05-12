# app/modules/identity/repositories/sessions.py
"""
登录会话仓储能力

本文件负责 auth_sessions 表读写。refresh token 是否可用、是否过期和是否需要轮换，
由 sessions 服务层判断，仓储层只保存事实。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select

from app.modules.identity.models import AuthSession
from app.shared.time import utc_now


class AuthSessionRepositoryMixin:
    """登录会话相关数据库操作。"""

    async def get_auth_session_by_id(self, auth_session_id: int) -> AuthSession | None:
        """按会话 ID 查找登录会话。"""

        return await self.session.get(AuthSession, auth_session_id)

    async def get_auth_session_by_refresh_hash(self, refresh_token_hash: str) -> AuthSession | None:
        """按 refresh token 哈希查找登录会话。"""

        statement = select(AuthSession).where(AuthSession.refresh_token_hash == refresh_token_hash)
        return await self.session.scalar(statement)

    async def create_auth_session(
        self,
        *,
        user_id: int,
        refresh_token_hash: str,
        channel: str,
        client_type: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthSession:
        """创建登录会话。"""

        now = utc_now()
        auth_session = AuthSession(
            user_id=user_id,
            refresh_token_hash=refresh_token_hash,
            channel=channel,
            client_type=client_type,
            status="active",
            expires_at=expires_at,
            last_used_at=now,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        self.session.add(auth_session)
        await self.session.flush()
        return auth_session

    async def rotate_auth_session(
        self,
        auth_session: AuthSession,
        *,
        refresh_token_hash: str,
        expires_at: datetime,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthSession:
        """轮换 refresh token，并刷新会话最后使用时间。"""

        now = utc_now()
        auth_session.refresh_token_hash = refresh_token_hash
        auth_session.expires_at = expires_at
        auth_session.last_used_at = now
        if user_agent is not None:
            auth_session.user_agent = user_agent
        if ip_address is not None:
            auth_session.ip_address = ip_address
        await self.session.flush()
        return auth_session

    async def revoke_auth_session(
        self,
        auth_session: AuthSession,
        *,
        reason: str,
    ) -> AuthSession:
        """撤销登录会话。"""

        now = utc_now()
        auth_session.status = "revoked"
        auth_session.revoked_at = now
        auth_session.revoke_reason = reason
        await self.session.flush()
        return auth_session
