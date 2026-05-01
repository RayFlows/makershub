# tests/test_identity.py
"""
身份领域服务测试

本文件验证内部用户主体、微信身份、本地账号、邮箱绑定和唯一 999 初始化等核心规则。
"""

from __future__ import annotations

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.base import Base
from app.core.errors import AppError
from app.core.security import hash_password, verify_password
from app.modules.identity.models import EmailVerificationCode, LocalAccount, User, WechatAccount
from app.modules.identity.service import (
    bind_verified_email_to_user,
    bootstrap_super_admin,
    login_wechat_identity,
    normalize_email,
)
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
    assert LocalAccount.__table__.c.password_hash.nullable is True


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


@pytest.mark.asyncio
async def test_wechat_login_creates_and_reuses_user_subject() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        first = await login_wechat_identity(
            session,
            openid="wx_openid_1",
            unionid=None,
            display_name="微信用户 A",
        )
        await session.commit()
        user_id = first.user.id

    async with session_factory() as session:
        second = await login_wechat_identity(
            session,
            openid="wx_openid_1",
            unionid="union_1",
        )
        await session.commit()

    assert first.created is True
    assert second.created is False
    assert second.user.id == user_id
    assert second.wechat_account.unionid == "union_1"

    await engine.dispose()


@pytest.mark.asyncio
async def test_wechat_login_rejects_unionid_conflict() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        await login_wechat_identity(session, openid="wx_openid_2", unionid="union_2")

        with pytest.raises(AppError, match="微信 unionid 已经绑定其他账号"):
            await login_wechat_identity(session, openid="wx_openid_3", unionid="union_2")

        with pytest.raises(AppError, match="微信 unionid 与已有账号不一致"):
            await login_wechat_identity(session, openid="wx_openid_2", unionid="union_changed")

    await engine.dispose()


@pytest.mark.asyncio
async def test_bind_verified_email_creates_pending_local_account() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        login = await login_wechat_identity(session, openid="wx_openid_4")
        result = await bind_verified_email_to_user(
            session,
            user_id=login.user.id,
            email=" Ray@Example.COM ",
        )
        await session.commit()

    assert result.created is True
    assert result.local_account.email == "ray@example.com"
    assert result.local_account.password_hash is None
    assert result.local_account.password_set_at is None
    assert result.local_account.email_verified_at is not None

    await engine.dispose()


@pytest.mark.asyncio
async def test_bind_verified_email_rejects_email_bound_to_another_user() -> None:
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        first = await login_wechat_identity(session, openid="wx_openid_5")
        second = await login_wechat_identity(session, openid="wx_openid_6")
        await bind_verified_email_to_user(
            session,
            user_id=first.user.id,
            email="ray@example.com",
        )

        with pytest.raises(AppError, match="该邮箱已经绑定其他用户"):
            await bind_verified_email_to_user(
                session,
                user_id=second.user.id,
                email="ray@example.com",
            )

    await engine.dispose()
