# app/modules/files/service.py
"""
文件元数据服务

本服务先提供稳定的对象 key 生成和元数据登记能力。真正的上传入口后续会在这里
协调 MinIO 客户端、权限校验和审计记录，业务模块不应自己拼对象存储路径。
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from pathlib import PurePath
from uuid import uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.models import FileObject
from app.modules.files.repository import FileRepository
from app.shared.time import utc_now

SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")


@dataclass(frozen=True)
class FileMetadataInput:
    """文件元数据登记参数。"""

    bucket: str
    object_key: str
    purpose: str
    owner_user_id: int | None = None
    original_filename: str | None = None
    content_type: str | None = None
    size_bytes: int = 0
    sha256: str | None = None
    visibility: str = "private"
    storage_provider: str = "minio"


def normalize_filename(filename: str | None) -> str:
    """
    生成适合对象存储路径使用的文件名片段。

    微信小程序曾经需要额外传 filename 来避免临时文件名和乱码问题。这里保留
    original_filename，同时对象 key 使用 ASCII 安全片段，降低不同客户端差异。
    """

    if not filename:
        return "file"

    path = PurePath(filename).name.strip()
    if not path:
        return "file"

    parsed = PurePath(path)
    ascii_stem = unicodedata.normalize("NFKD", parsed.stem).encode("ascii", "ignore").decode()
    ascii_stem = SAFE_FILENAME_PATTERN.sub("_", ascii_stem).strip("._-") or "file"
    ascii_suffix = SAFE_FILENAME_PATTERN.sub("", parsed.suffix.lower())
    return f"{ascii_stem}{ascii_suffix}"


def build_object_key(
    *,
    purpose: str,
    owner_user_id: int | None = None,
    filename: str | None = None,
    now: datetime | None = None,
) -> str:
    """
    构造统一对象存储 key。

    key 中包含用途、可选用户 ID、时间和随机段，避免不同业务模块各自发明命名规则。
    """

    current = now or utc_now()
    safe_purpose = SAFE_FILENAME_PATTERN.sub("_", purpose.strip().lower()).strip("._-") or "general"
    safe_name = normalize_filename(filename)
    random_part = uuid4().hex[:16]
    timestamp = current.strftime("%Y%m%d%H%M%S")

    if owner_user_id is None:
        return f"{safe_purpose}/{timestamp}_{random_part}_{safe_name}"
    return f"{safe_purpose}/users/{owner_user_id}/{timestamp}_{random_part}_{safe_name}"


def calculate_sha256(file_data: bytes) -> str:
    """计算文件内容 sha256，用于后续去重、审计和完整性校验。"""

    return hashlib.sha256(file_data).hexdigest()


async def register_file_metadata(
    session: AsyncSession,
    metadata: FileMetadataInput,
) -> FileObject:
    """
    登记已经写入对象存储的文件元数据。

    Args:
        session: 当前业务事务使用的数据库会话。
        metadata: 文件元数据参数。

    Returns:
        已加入当前事务的 FileObject。
    """

    repository = FileRepository(session)
    file_object = FileObject(
        owner_user_id=metadata.owner_user_id,
        purpose=metadata.purpose,
        visibility=metadata.visibility,
        storage_provider=metadata.storage_provider,
        bucket=metadata.bucket,
        object_key=metadata.object_key,
        original_filename=metadata.original_filename,
        content_type=metadata.content_type,
        size_bytes=metadata.size_bytes,
        sha256=metadata.sha256,
        status="active",
    )
    return await repository.add(file_object)
