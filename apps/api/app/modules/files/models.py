# app/modules/files/models.py
"""
文件元数据数据库模型

旧系统在用户头像、活动海报和项目材料里直接保存 MinIO 对象名。重构后统一由
files 表保存对象存储元数据，业务表只引用 file_id，方便后续做权限、审计、
清理临时文件和对象迁移。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.base import Base, IdMixin, TimestampMixin
from app.shared.time import utc_now

file_size_type = BigInteger().with_variant(Integer, "sqlite")


class FileObject(Base, IdMixin, TimestampMixin):
    """
    文件元数据表。

    这张表只记录对象存储元数据和业务引用线索，不直接保存文件内容。
    """

    __tablename__ = "files"

    # --- 归属与用途 ---
    owner_user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=True,
        index=True,
    )
    purpose: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(32), nullable=False, default="private", index=True)

    # --- 对象存储定位 ---
    storage_provider: Mapped[str] = mapped_column(String(32), nullable=False, default="minio")
    bucket: Mapped[str] = mapped_column(String(128), nullable=False)
    object_key: Mapped[str] = mapped_column(String(512), nullable=False)

    # --- 文件属性 ---
    original_filename: Mapped[str | None] = mapped_column(String(255), nullable=True)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int] = mapped_column(file_size_type, nullable=False, default=0)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)

    # --- 生命周期 ---
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active", index=True)
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: utc_now(),
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    __table_args__ = (
        UniqueConstraint("bucket", "object_key", name="uq_files_bucket_object_key"),
        Index("ix_files_owner_status", "owner_user_id", "status"),
        Index("ix_files_purpose_status", "purpose", "status"),
    )
