# migrations/env.py
"""
Alembic 迁移运行环境

该文件由 Alembic 调用，用于读取数据库连接、加载 ORM 元数据并执行迁移。
项目使用 SQLAlchemy AsyncEngine，因此在线迁移需要通过 run_sync 桥接到同步迁移上下文。
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config.settings import get_settings
from app.core.database.base import Base
from app.core.permissions import models as permission_models  # noqa: F401
from app.modules.audit import models as audit_models  # noqa: F401
from app.modules.borrowing import models as borrowing_models  # noqa: F401
from app.modules.files import models as file_models  # noqa: F401
from app.modules.identity import models as identity_models  # noqa: F401
from app.modules.organization import models as organization_models  # noqa: F401
from app.modules.points import models as point_models  # noqa: F401
from app.modules.resources import models as resource_models  # noqa: F401
from app.modules.workbench import models as workbench_models  # noqa: F401

# --- Alembic 基础配置 ---
config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Base.metadata 会收集所有已导入模型，用于 autogenerate 对比数据库结构。
target_metadata = Base.metadata


def get_database_url() -> str:
    """从运行时配置读取数据库连接。"""

    return get_settings().database_url


def run_migrations_offline() -> None:
    """
    离线迁移模式。

    该模式不创建数据库连接，只根据 URL 生成 SQL。当前主要保留 Alembic 标准能力。
    """

    context.configure(
        url=get_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    """在同步连接上下文中执行迁移。"""

    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """
    在线迁移模式。

    Alembic 的迁移上下文是同步 API，而项目数据库连接是异步 engine，
    所以这里先创建 AsyncEngine，再通过 connection.run_sync 执行同步迁移函数。
    """

    configuration = config.get_section(config.config_ini_section, {})
    configuration["sqlalchemy.url"] = get_database_url()

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """启动异步在线迁移。"""

    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
