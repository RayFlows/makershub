# tests/test_files.py
"""
文件元数据基础设施测试

文件模块先验证对象 key 生成、hash 计算和 files 表元数据登记。实际上传到 MinIO
会在统一上传接口落地时再做集成测试。
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database.base import Base
from app.core.errors import AppError
from app.modules.files.service import (
    FileMetadataInput,
    FileUploadIntentInput,
    build_object_key,
    calculate_sha256,
    create_file_upload_intent,
    normalize_filename,
    register_file_metadata,
    validate_upload_intent,
)
from app.modules.identity.models import User


def test_build_object_key_uses_stable_safe_segments() -> None:
    """对象 key 应该包含用途、用户、时间和安全文件名。"""

    key = build_object_key(
        purpose="Project Material",
        owner_user_id=7,
        filename="结项报告 final.pdf",
        now=datetime(2026, 5, 2, 12, 0, 0, tzinfo=UTC),
    )

    assert key.startswith("project_material/users/7/20260502120000_")
    assert key.endswith("_final.pdf")
    assert normalize_filename("../头像.png") == "file.png"


def test_calculate_sha256_returns_hex_digest() -> None:
    """文件 hash 用于后续完整性校验和审计线索。"""

    assert calculate_sha256(b"makershub") == (
        "30028d13bfc1bac3a86817f1ba4ae523f6db675d2a880352d2bf98cedb5f51e4"
    )


def test_validate_upload_intent_rejects_unsupported_content_type() -> None:
    """上传意图必须按用途限制文件类型。"""

    with pytest.raises(AppError, match="当前文件类型不允许上传") as exc_info:
        validate_upload_intent(
            FileUploadIntentInput(
                purpose="project_material",
                original_filename="run.exe",
                content_type="application/x-msdownload",
                size_bytes=1024,
            ),
        )

    assert exc_info.value.code == "FILE_CONTENT_TYPE_UNSUPPORTED"


@pytest.mark.asyncio
async def test_register_file_metadata_persists_file_record() -> None:
    """文件服务应该能登记已上传对象的元数据。"""

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _ = User
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        file_object = await register_file_metadata(
            session,
            FileMetadataInput(
                bucket="makershub-projects-local",
                object_key="projects/test.pdf",
                purpose="project_material",
                original_filename="test.pdf",
                content_type="application/pdf",
                size_bytes=1024,
                sha256="0" * 64,
            ),
        )
        await session.commit()

    assert file_object.id is not None
    assert file_object.bucket == "makershub-projects-local"
    assert file_object.object_key == "projects/test.pdf"
    assert file_object.status == "active"

    await engine.dispose()


@pytest.mark.asyncio
async def test_create_file_upload_intent_registers_pending_metadata(monkeypatch) -> None:
    """上传意图应该先登记 pending_upload 文件元数据并返回短期 PUT URL。"""

    class FakeMinioClient:
        """测试用 MinIO 客户端。"""

        def presigned_put_object(self, bucket_name, object_name, *, expires):
            assert bucket_name == "makershub-projects-local"
            assert object_name.startswith("project_material/users/9/")
            assert expires.total_seconds() == 900
            return f"https://upload.example.com/{object_name}"

    monkeypatch.setattr("app.modules.files.service.create_minio_client", lambda: FakeMinioClient())

    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    _ = User
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await create_file_upload_intent(
            session,
            owner_user_id=9,
            payload=FileUploadIntentInput(
                purpose="project_material",
                original_filename="开源协议.pdf",
                content_type="application/pdf",
                size_bytes=2048,
            ),
        )
        await session.commit()

    assert result.method == "PUT"
    assert result.expires_in == 900
    assert result.file_object.id is not None
    assert result.file_object.status == "pending_upload"
    assert result.file_object.bucket == "makershub-projects-local"
    assert result.file_object.content_type == "application/pdf"
    assert result.upload_url.startswith("https://upload.example.com/project_material/users/9/")

    await engine.dispose()
