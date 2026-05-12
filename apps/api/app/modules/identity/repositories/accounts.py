# app/modules/identity/repositories/accounts.py
"""
身份账号仓储能力

本文件负责微信身份和邮箱密码账号的读写。它不判断业务流程是否允许执行，
例如普通用户能否先注册网页账号仍由 accounts 服务层控制。
"""

from __future__ import annotations

from sqlalchemy import func, select

from app.modules.identity.models import EmailPasswordAccount, User, WechatAccount
from app.shared.time import utc_now


class EmailPasswordAccountRepositoryMixin:
    """邮箱密码账号相关数据库操作。"""

    async def get_email_password_account_by_email(self, email: str) -> EmailPasswordAccount | None:
        """按邮箱查找邮箱密码账号，大小写不敏感。"""

        statement = select(EmailPasswordAccount).where(func.lower(EmailPasswordAccount.email) == email.lower())
        return await self.session.scalar(statement)

    async def get_email_password_account_by_user_id(self, user_id: int) -> EmailPasswordAccount | None:
        """按用户主体 ID 查找邮箱密码账号。"""

        statement = select(EmailPasswordAccount).where(EmailPasswordAccount.user_id == user_id)
        return await self.session.scalar(statement)

    async def create_email_password_user(
        self,
        *,
        email: str,
        password_hash: str,
        display_name: str,
    ) -> tuple[User, EmailPasswordAccount]:
        """创建带密码的邮箱密码账号用户。

        目前只用于第一个 999 初始化；普通用户不能通过网页端直接调用这个流程注册。
        """

        now = utc_now()
        user = User(display_name=display_name, status="active")
        account = EmailPasswordAccount(
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

    async def create_pending_email_password_account(
        self,
        *,
        user: User,
        email: str,
    ) -> EmailPasswordAccount:
        """为已存在的微信用户主体创建待设置密码的邮箱账号。"""

        now = utc_now()
        account = EmailPasswordAccount(
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

    async def set_email_password_account_password(
        self,
        account: EmailPasswordAccount,
        *,
        password_hash: str,
    ) -> EmailPasswordAccount:
        """设置邮箱密码登录密码。"""

        now = utc_now()
        account.password_hash = password_hash
        account.password_set_at = now
        await self.session.flush()
        return account


class WechatAccountRepositoryMixin:
    """微信账号相关数据库操作。"""

    async def get_wechat_account_by_openid(self, openid: str) -> WechatAccount | None:
        """按微信 openid 查找微信账号。"""

        statement = select(WechatAccount).where(WechatAccount.openid == openid)
        return await self.session.scalar(statement)

    async def get_wechat_account_by_unionid(self, unionid: str) -> WechatAccount | None:
        """按微信 unionid 查找微信账号。"""

        statement = select(WechatAccount).where(WechatAccount.unionid == unionid)
        return await self.session.scalar(statement)

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
        """记录一次微信登录，并在首次拿到 unionid 时补写。"""

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
