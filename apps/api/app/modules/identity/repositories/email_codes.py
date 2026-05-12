# app/modules/identity/repositories/email_codes.py
"""
邮箱验证码仓储能力

本文件只负责验证码记录的查询和写入；验证码用途、频率限制和哈希策略由
email_codes 服务层控制。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import func, select

from app.modules.identity.models import EmailVerificationCode
from app.shared.time import utc_now


class EmailVerificationCodeRepositoryMixin:
    """邮箱验证码相关数据库操作。"""

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
