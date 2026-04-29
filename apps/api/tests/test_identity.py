from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.base import Base
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.modules.identity.models import EmailVerificationCode, LocalAccount, User, WechatAccount
from app.modules.identity.service import bootstrap_super_admin, normalize_email
from app.modules.organization.models import Position, UserPosition


def test_password_hash_round_trip() -> None:
    password_hash = hash_password("correct-horse-battery")

    assert password_hash != "correct-horse-battery"
    assert verify_password("correct-horse-battery", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_identity_metadata_contains_expected_tables() -> None:
    assert User.__tablename__ in Base.metadata.tables
    assert LocalAccount.__tablename__ in Base.metadata.tables
    assert WechatAccount.__tablename__ in Base.metadata.tables
    assert EmailVerificationCode.__tablename__ in Base.metadata.tables
    assert Position.__tablename__ in Base.metadata.tables
    assert UserPosition.__tablename__ in Base.metadata.tables


def test_normalize_email() -> None:
    assert normalize_email(" Ray@Example.COM ") == "ray@example.com"


@pytest.mark.asyncio
async def test_bootstrap_super_admin_creates_user_account_and_position() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await bootstrap_super_admin(
            session,
            email="Ray@Example.COM",
            password="super-safe-password",
            display_name="Ray",
        )
        await session.commit()

    async with session_factory() as session:
        account = await session.scalar(select(LocalAccount))
        position = await session.scalar(select(Position).where(Position.code == "999"))
        user_position = await session.scalar(select(UserPosition))

    assert result.created is True
    assert account is not None
    assert account.email == "ray@example.com"
    assert position is not None
    assert position.is_system is True
    assert user_position is not None
    assert user_position.scope_type == "global"

    await engine.dispose()


@pytest.mark.asyncio
async def test_bootstrap_super_admin_rejects_duplicate_active_999() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await bootstrap_super_admin(
            session,
            email="ray@example.com",
            password="super-safe-password",
            display_name="Ray",
        )
        await session.commit()

    async with session_factory() as session:
        with pytest.raises(AppError, match="系统中已经存在有效的 999 超级管理员"):
            await bootstrap_super_admin(
                session,
                email="other@example.com",
                password="another-safe-password",
                display_name="Other",
            )

    await engine.dispose()
