# tests/support/context.py
"""
HTTP 接口测试上下文

本文件提供基于临时 SQLite 数据库的 `TestClient` 创建工具。它只处理测试基础设施：
建表、权限种子同步、FastAPI 数据库依赖覆盖和资源释放；业务数据 seed 由调用方传入。
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database import get_session
from app.core.database.base import Base
from app.core.permissions.service import sync_registered_permissions
from app.main import create_app

SeedDatabase = Callable[[AsyncSession], Awaitable[None]]


@dataclass(frozen=True)
class ApiTestContext:
    """HTTP 接口测试上下文。"""

    client: TestClient
    session_factory: async_sessionmaker[AsyncSession]


@contextmanager
def api_test_context(
    tmp_path: Path,
    *,
    database_name: str,
    model_refs: Iterable[Any] = (),
    seed: SeedDatabase | None = None,
    sync_permissions: bool = True,
) -> Iterator[ApiTestContext]:
    """
    创建使用临时 SQLite 文件数据库的接口测试上下文。

    Args:
        tmp_path: pytest 提供的临时目录。
        database_name: 当前测试数据库文件名。
        model_refs: 显式引用的 ORM 模型，确保 `Base.metadata` 已收集相关表。
        seed: 可选业务种子函数，在权限同步前写入基础数据。
        sync_permissions: 是否同步权限点和预置角色。
    """

    # 保留对模型类的显式引用，避免维护者误删测试文件中的模型导入。
    _ = tuple(model_refs)

    database_path = tmp_path / database_name
    engine = create_async_engine(f"sqlite+aiosqlite:///{database_path}")
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async def prepare_database() -> None:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with session_factory() as session:
            if seed is not None:
                await seed(session)
            if sync_permissions:
                await sync_registered_permissions(session)
            await session.commit()

    async def override_get_session() -> AsyncIterator[AsyncSession]:
        async with session_factory() as session:
            yield session

    asyncio.run(prepare_database())
    app = create_app()
    app.dependency_overrides[get_session] = override_get_session

    try:
        with TestClient(app) as client:
            yield ApiTestContext(client=client, session_factory=session_factory)
    finally:
        app.dependency_overrides.clear()
        asyncio.run(engine.dispose())
