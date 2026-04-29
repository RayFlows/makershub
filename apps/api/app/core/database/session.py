# app/core/database/session.py
"""
数据库连接与会话管理

本文件负责创建全局异步 engine、异步 Session 工厂，以及 FastAPI 依赖注入使用的
数据库会话。业务代码不应该自己创建 engine，避免连接池分散、事务边界混乱。

主要功能:
1. 根据 Settings 创建 SQLAlchemy AsyncEngine；
2. 提供每个请求独立使用的 AsyncSession；
3. 提供健康检查使用的数据库 ping；
4. 应用关闭时释放数据库连接池。
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config.settings import get_settings

# --- 全局数据库引擎 ---
# Settings 使用 lru_cache 缓存，这里读取一次即可；测试如需替换配置，应在进程级别处理。
settings = get_settings()

engine = create_async_engine(
    settings.database_url,
    echo=settings.database_echo,
    pool_pre_ping=True,  # 每次取连接前先探活，减少 MySQL 空闲连接断开带来的偶发错误
)

# --- Session 工厂 ---
# expire_on_commit=False 可以避免 commit 后 ORM 对象属性被过期，服务层返回结果时更稳定。
# autoflush=False 让 flush 边界更明确，避免查询时隐式写库。
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    expire_on_commit=False,
    autoflush=False,
)


async def get_session() -> AsyncIterator[AsyncSession]:
    """
    FastAPI 数据库会话依赖。

    每个请求创建一个独立 AsyncSession，请求结束后自动关闭连接。
    事务提交/回滚由具体接口或服务层显式控制，避免隐藏副作用。
    """

    async with AsyncSessionLocal() as session:
        yield session


async def ping_database() -> None:
    """
    数据库健康检查。

    readiness 接口会调用该函数。只执行轻量 SELECT 1，不触发业务表查询。
    """

    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def close_database_engine() -> None:
    """
    关闭数据库连接池。

    应用生命周期结束时调用，确保 Docker/测试环境里不会留下悬挂连接。
    """

    await engine.dispose()
