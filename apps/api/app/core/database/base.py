# app/core/database/base.py
"""
SQLAlchemy 声明式基类与通用字段

所有 ORM 模型都应该继承 Base，并尽量复用这里的 mixin。
该文件定义统一的约束命名规则，保证 Alembic 自动迁移生成的索引、外键和唯一约束
在不同环境中名称稳定，便于回滚和排查数据库问题。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, MetaData, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# --- Alembic 约束命名规则 ---
# 不显式指定命名规则时，不同数据库可能生成不同的约束名称。
# 统一命名后，迁移脚本在开发、预发布和生产环境中更可控。
NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """项目统一 ORM 基类。"""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


# --- 主键类型 ---
# MySQL 使用 BigInteger，SQLite 测试环境使用 Integer，避免内存库自增行为差异。
id_type = BigInteger().with_variant(Integer, "sqlite")


class IdMixin:
    """统一自增主键字段。"""

    id: Mapped[int] = mapped_column(id_type, primary_key=True, autoincrement=True)


class TimestampMixin:
    """统一创建和更新时间字段。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """软删除字段。

    重要业务数据不直接物理删除，后续查询层会结合 deleted_at 处理可见性。
    """

    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
