# app/modules/identity/repository.py
"""
身份域数据访问层

Repository 只封装数据库读写，不决定业务是否允许执行。
业务规则放在 service.py，避免查询方法里混入权限和流程判断。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.modules.identity.models import (
    AuthSession,
    EmailVerificationCode,
    LocalAccount,
    User,
    WechatAccount,
)
from app.modules.organization.models import Position, UserPosition
from app.shared.time import utc_now


class IdentityRepository:
    """身份域数据库操作集合。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_local_account_by_email(self, email: str) -> LocalAccount | None:
        """按邮箱查找本地账号，大小写不敏感。"""

        statement = select(LocalAccount).where(func.lower(LocalAccount.email) == email.lower())
        return await self.session.scalar(statement)

    async def get_local_account_by_user_id(self, user_id: int) -> LocalAccount | None:
        """按用户主体 ID 查找本地账号。"""

        statement = select(LocalAccount).where(LocalAccount.user_id == user_id)
        return await self.session.scalar(statement)

    async def get_wechat_account_by_openid(self, openid: str) -> WechatAccount | None:
        """按微信 openid 查找微信账号。"""

        statement = select(WechatAccount).where(WechatAccount.openid == openid)
        return await self.session.scalar(statement)

    async def get_wechat_account_by_unionid(self, unionid: str) -> WechatAccount | None:
        """按微信 unionid 查找微信账号。"""

        statement = select(WechatAccount).where(WechatAccount.unionid == unionid)
        return await self.session.scalar(statement)

    async def get_user_by_id(self, user_id: int) -> User | None:
        """按内部用户主键查找用户主体。"""

        statement = select(User).options(selectinload(User.local_account)).where(User.id == user_id)
        return await self.session.scalar(statement)

    async def get_auth_session_by_id(self, auth_session_id: int) -> AuthSession | None:
        """按会话 ID 查找登录会话。"""

        return await self.session.get(AuthSession, auth_session_id)

    async def get_auth_session_by_refresh_hash(self, refresh_token_hash: str) -> AuthSession | None:
        """按 refresh token 哈希查找登录会话。"""

        statement = select(AuthSession).where(AuthSession.refresh_token_hash == refresh_token_hash)
        return await self.session.scalar(statement)

    async def get_latest_email_verification_code(
        self,
        *,
        email: str,
        purpose: str,
        user_id: int | None,
    ) -> EmailVerificationCode | None:
        """查找某邮箱某用途最近一次验证码记录。"""

        statement = (
            select(EmailVerificationCode)
            .where(
                func.lower(EmailVerificationCode.email) == email.lower(),
                EmailVerificationCode.purpose == purpose,
            )
            .order_by(EmailVerificationCode.created_at.desc())
        )
        if user_id is None:
            statement = statement.where(EmailVerificationCode.user_id.is_(None))
        else:
            statement = statement.where(EmailVerificationCode.user_id == user_id)
        return await self.session.scalar(statement)

    async def count_email_verification_codes_since(
        self,
        *,
        email: str,
        purpose: str,
        since: datetime,
    ) -> int:
        """统计某邮箱某用途在指定时间后的验证码发送次数。"""

        statement = select(func.count(EmailVerificationCode.id)).where(
            func.lower(EmailVerificationCode.email) == email.lower(),
            EmailVerificationCode.purpose == purpose,
            EmailVerificationCode.created_at >= since,
        )
        return await self.session.scalar(statement) or 0

    async def get_usable_email_verification_code(
        self,
        *,
        email: str,
        purpose: str,
        code_hash: str,
        user_id: int | None,
        now: datetime,
    ) -> EmailVerificationCode | None:
        """查找可消费的邮箱验证码。"""

        statement = (
            select(EmailVerificationCode)
            .where(
                func.lower(EmailVerificationCode.email) == email.lower(),
                EmailVerificationCode.purpose == purpose,
                EmailVerificationCode.code_hash == code_hash,
                EmailVerificationCode.consumed_at.is_(None),
                EmailVerificationCode.expires_at > now,
            )
            .order_by(EmailVerificationCode.created_at.desc())
        )
        if user_id is None:
            statement = statement.where(EmailVerificationCode.user_id.is_(None))
        else:
            statement = statement.where(EmailVerificationCode.user_id == user_id)
        return await self.session.scalar(statement)

    async def get_active_super_admin_position(self) -> UserPosition | None:
        """查找当前系统中是否已经存在有效 999。"""

        statement = (
            select(UserPosition)
            .join(Position, UserPosition.position_id == Position.id)
            .where(Position.code == "999", UserPosition.revoked_at.is_(None))
        )
        return await self.session.scalar(statement)

    async def get_position_by_code(self, code: str) -> Position | None:
        """按职务代码查找职务定义。"""

        statement = select(Position).where(Position.code == code)
        return await self.session.scalar(statement)

    async def create_local_user(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> tuple[User, LocalAccount]:
        """创建带密码的本地账号用户。

        目前只用于第一个 999 初始化；普通用户不能通过网页端直接调用这个流程注册。
        """

        now = utc_now()
        user = User(display_name=display_name, status="active")
        account = LocalAccount(
            user=user,
            email=email,
            password_hash=password_hash,
            password_set_at=now,
            email_verified_at=now,
            status="active",
        )
        self.session.add(user)
        self.session.add(account)
        await self.session.flush()
        return user, account

    async def create_wechat_user(
        self,
        *,
        openid: str,
        unionid: str | None,
        session_key_hash: str | None,
        display_name: str,
    ) -> tuple[User, WechatAccount]:
        """小程序首次微信登录时创建用户主体和微信凭证。"""

        now = utc_now()
        user = User(display_name=display_name, status="active", last_login_at=now)
        account = WechatAccount(
            user=user,
            openid=openid,
            unionid=unionid,
            session_key_hash=session_key_hash,
            bound_at=now,
            status="active",
        )
        self.session.add(user)
        self.session.add(account)
        await self.session.flush()
        return user, account

    async def mark_wechat_login(
        self,
        account: WechatAccount,
        *,
        unionid: str | None,
        session_key_hash: str | None,
    ) -> User:
        """记录一次微信登录，并在首次拿到 unionid 时补写。

        unionid 冲突判断在 service 层完成，这里只做字段更新和 last_login_at 刷新。
        """

        now = utc_now()
        if unionid and account.unionid is None:
            account.unionid = unionid
        if session_key_hash is not None:
            account.session_key_hash = session_key_hash

        user = await self.get_user_by_id(account.user_id)
        if user is None:
            raise RuntimeError("wechat account has no user")
        user.last_login_at = now
        await self.session.flush()
        return user

    async def create_pending_local_account(
        self,
        *,
        user: User,
        email: str,
    ) -> LocalAccount:
        """为已存在的微信用户主体创建待设置密码的邮箱账号。"""

        now = utc_now()
        account = LocalAccount(
            user=user,
            email=email,
            password_hash=None,
            password_set_at=None,
            email_verified_at=now,
            status="active",
        )
        self.session.add(account)
        await self.session.flush()
        return account

    async def create_email_verification_code(
        self,
        *,
        email: str,
        purpose: str,
        code_hash: str,
        expires_at: datetime,
        request_ip: str | None,
        user_id: int | None,
    ) -> EmailVerificationCode:
        """创建邮箱验证码记录。"""

        record = EmailVerificationCode(
            email=email,
            purpose=purpose,
            code_hash=code_hash,
            expires_at=expires_at,
            request_ip=request_ip,
            user_id=user_id,
        )
        self.session.add(record)
        await self.session.flush()
        return record

    async def consume_email_verification_code(
        self,
        record: EmailVerificationCode,
    ) -> EmailVerificationCode:
        """标记邮箱验证码已经消费。"""

        record.consumed_at = utc_now()
        await self.session.flush()
        return record

    async def set_local_account_password(
        self,
        account: LocalAccount,
        *,
        password_hash: str,
    ) -> LocalAccount:
        """设置本地账号密码。"""

        now = utc_now()
        account.password_hash = password_hash
        account.password_set_at = now
        await self.session.flush()
        return account

    async def mark_user_login(self, user: User) -> User:
        """刷新用户最近登录时间。"""

        user.last_login_at = utc_now()
        await self.session.flush()
        return user

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
