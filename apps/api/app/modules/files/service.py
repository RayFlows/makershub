# app/modules/files/service.py
"""
文件元数据服务

本服务提供稳定的对象 key 生成、上传意图创建和元数据登记能力。业务模块只应引用
file_id 并补充自己的业务归属校验，不应自己拼对象存储路径或绕过上传安全策略。
"""

from __future__ import annotations

import asyncio
import hashlib
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import PurePath
from uuid import uuid4

from minio.error import S3Error
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config.settings import get_settings
from app.core.errors import AppError
from app.infrastructure.minio import create_minio_client
from app.modules.files.models import FileObject
from app.modules.files.repository import FileRepository
from app.shared.time import utc_now

SAFE_FILENAME_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")
UPLOAD_URL_EXPIRES_IN_SECONDS = 15 * 60
BLOCKED_UPLOAD_SUFFIXES = {
    ".bat",
    ".cmd",
    ".com",
    ".exe",
    ".js",
    ".msi",
    ".ps1",
    ".scr",
    ".sh",
    ".vbs",
}


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
    status: str = "active"


@dataclass(frozen=True)
class UploadPurposePolicy:
    """上传用途安全策略。"""

    purpose: str
    bucket_name: str
    allowed_content_types: tuple[str, ...]
    max_size_bytes: int
    visibility: str = "private"


@dataclass(frozen=True)
class FileUploadIntentInput:
    """创建上传意图的输入参数。"""

    purpose: str
    original_filename: str
    content_type: str
    size_bytes: int


@dataclass(frozen=True)
class FileUploadIntentResult:
    """上传意图创建结果。"""

    file_object: FileObject
    upload_url: str
    expires_in: int
    method: str = "PUT"


@dataclass(frozen=True)
class FileUploadCompletionResult:
    """上传完成复核结果。"""

    file_object: FileObject
    sha256: str


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


def normalize_upload_purpose(purpose: str) -> str:
    """规范化上传用途。"""

    normalized = purpose.strip().lower()
    normalized = SAFE_FILENAME_PATTERN.sub("_", normalized).strip("._-")
    if not normalized:
        raise AppError("FILE_PURPOSE_REQUIRED", "文件用途不能为空", status_code=422)
    return normalized


def normalize_content_type(content_type: str) -> str:
    """规范化 Content-Type。"""

    normalized = content_type.split(";", maxsplit=1)[0].strip().lower()
    if "/" not in normalized or len(normalized) > 128:
        raise AppError("FILE_CONTENT_TYPE_INVALID", "文件 Content-Type 不合法", status_code=422)
    return normalized


def get_upload_policies() -> dict[str, UploadPurposePolicy]:
    """读取当前环境下允许的上传用途策略。"""

    settings = get_settings()
    return {
        "avatar": UploadPurposePolicy(
            purpose="avatar",
            bucket_name=settings.minio_avatar_bucket,
            allowed_content_types=("image/jpeg", "image/png", "image/webp"),
            max_size_bytes=2 * 1024 * 1024,
            visibility="private",
        ),
        "project_material": UploadPurposePolicy(
            purpose="project_material",
            bucket_name=settings.minio_project_bucket,
            allowed_content_types=("application/pdf", "image/jpeg", "image/png", "application/zip"),
            max_size_bytes=20 * 1024 * 1024,
        ),
        "resource_attachment": UploadPurposePolicy(
            purpose="resource_attachment",
            bucket_name=settings.minio_resource_bucket,
            allowed_content_types=("application/pdf", "image/jpeg", "image/png"),
            max_size_bytes=10 * 1024 * 1024,
        ),
        "temp": UploadPurposePolicy(
            purpose="temp",
            bucket_name=settings.minio_temp_bucket,
            allowed_content_types=("application/pdf", "image/jpeg", "image/png"),
            max_size_bytes=5 * 1024 * 1024,
        ),
    }


def get_upload_policy(purpose: str) -> UploadPurposePolicy:
    """根据用途读取上传安全策略。"""

    normalized_purpose = normalize_upload_purpose(purpose)
    policy = get_upload_policies().get(normalized_purpose)
    if policy is None:
        raise AppError("FILE_PURPOSE_UNSUPPORTED", "当前文件用途暂未开放上传", status_code=422)
    return policy


def validate_upload_intent(payload: FileUploadIntentInput) -> tuple[UploadPurposePolicy, str, str]:
    """
    校验上传意图。

    统一上传入口必须先校验用途、文件名、大小和 Content-Type，业务模块不能绕过这里
    直接向对象存储写入任意文件。
    """

    policy = get_upload_policy(payload.purpose)
    normalized_content_type = normalize_content_type(payload.content_type)
    normalized_filename = normalize_filename(payload.original_filename)
    suffix = PurePath(normalized_filename).suffix.lower()

    if payload.size_bytes <= 0:
        raise AppError("FILE_SIZE_INVALID", "文件大小必须大于 0", status_code=422)
    if payload.size_bytes > policy.max_size_bytes:
        raise AppError(
            "FILE_SIZE_EXCEEDED",
            "文件大小超过当前用途限制",
            status_code=413,
            details={"max_size_bytes": policy.max_size_bytes},
        )
    if normalized_content_type not in policy.allowed_content_types:
        raise AppError(
            "FILE_CONTENT_TYPE_UNSUPPORTED",
            "当前文件类型不允许上传",
            status_code=422,
            details={"allowed_content_types": list(policy.allowed_content_types)},
        )
    if suffix in BLOCKED_UPLOAD_SUFFIXES:
        raise AppError("FILE_SUFFIX_BLOCKED", "当前文件后缀不允许上传", status_code=422)
    return policy, normalized_filename, normalized_content_type


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


def calculate_minio_object_sha256(client, bucket_name: str, object_key: str) -> str:
    """
    流式计算对象存储中文件的 sha256。

    MinIO Python SDK 是同步客户端，这个函数会被放到线程池里执行。这里显式关闭
    response，避免校验完成后 HTTP 连接泄漏。
    """

    response = client.get_object(bucket_name, object_key)
    try:
        digest = hashlib.sha256()
        for chunk in response.stream(32 * 1024):
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        response.close()
        response.release_conn()


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
        status=metadata.status,
    )
    return await repository.add(file_object)


async def create_file_upload_intent(
    session: AsyncSession,
    *,
    owner_user_id: int,
    payload: FileUploadIntentInput,
) -> FileUploadIntentResult:
    """
    创建预签名上传意图。

    该函数只开放 PUT 到指定对象 key 的短期 URL，并先登记 pending_upload 文件元数据。
    真正的业务归属和审核仍由项目、资源、头像等业务模块引用 file_id 后继续处理。
    """

    policy, safe_filename, normalized_content_type = validate_upload_intent(payload)
    object_key = build_object_key(
        purpose=policy.purpose,
        owner_user_id=owner_user_id,
        filename=safe_filename,
    )
    file_object = await register_file_metadata(
        session,
        FileMetadataInput(
            owner_user_id=owner_user_id,
            purpose=policy.purpose,
            visibility=policy.visibility,
            bucket=policy.bucket_name,
            object_key=object_key,
            original_filename=payload.original_filename,
            content_type=normalized_content_type,
            size_bytes=payload.size_bytes,
            status="pending_upload",
        ),
    )

    client = create_minio_client()
    upload_url = client.presigned_put_object(
        policy.bucket_name,
        object_key,
        expires=timedelta(seconds=UPLOAD_URL_EXPIRES_IN_SECONDS),
    )
    return FileUploadIntentResult(
        file_object=file_object,
        upload_url=upload_url,
        expires_in=UPLOAD_URL_EXPIRES_IN_SECONDS,
    )


def normalize_uploaded_object_content_type(content_type: str | None) -> str:
    """规范化对象存储返回的 Content-Type，空值保留为空字符串用于差异提示。"""

    if not content_type:
        return ""
    try:
        return normalize_content_type(content_type)
    except AppError as exc:
        raise AppError(
            "FILE_UPLOAD_CONTENT_TYPE_MISMATCH",
            "对象存储中的文件类型与上传意图不一致",
            status_code=409,
            details={"actual_content_type": content_type},
        ) from exc


async def inspect_uploaded_object(client, bucket_name: str, object_key: str):
    """
    读取对象存储中的对象元信息。

    上传完成接口必须以对象存储里的真实对象为准，不能只相信客户端传回的成功状态。
    """

    try:
        return await asyncio.to_thread(client.stat_object, bucket_name, object_key)
    except S3Error as exc:
        if exc.code in {"NoSuchKey", "NoSuchObject", "NotFound"}:
            raise AppError(
                "FILE_UPLOAD_OBJECT_MISSING",
                "对象存储中尚未找到该文件，请确认上传完成后再提交",
                status_code=409,
            ) from exc
        raise AppError(
            "FILE_STORAGE_VERIFY_FAILED",
            "对象存储校验失败，请稍后重试",
            status_code=502,
            details={"storage_error": exc.code},
        ) from exc


async def complete_file_upload(
    session: AsyncSession,
    *,
    owner_user_id: int,
    file_id: int,
    expected_sha256: str | None = None,
) -> FileUploadCompletionResult:
    """
    完成上传并复核对象存储中的真实文件。

    预签名上传是两段式流程：创建意图只登记“允许写入哪里”，完成接口才确认
    “对象确实写入、大小和类型未被篡改、hash 已落库”。业务模块只能引用
    `active` 状态的文件，不能直接消费 `pending_upload`。
    """

    repository = FileRepository(session)
    file_object = await repository.get_by_id(file_id)
    if file_object is None:
        raise AppError("FILE_NOT_FOUND", "文件记录不存在", status_code=404)
    if file_object.owner_user_id != owner_user_id:
        raise AppError("FILE_ACCESS_DENIED", "无权操作该文件", status_code=403)
    if file_object.status == "active":
        if file_object.sha256 is None:
            raise AppError("FILE_UPLOAD_STATE_INVALID", "文件状态异常，缺少完整性校验结果", status_code=409)
        if expected_sha256 is not None and file_object.sha256.lower() != expected_sha256.lower():
            raise AppError(
                "FILE_UPLOAD_HASH_MISMATCH",
                "对象存储中的文件 hash 与客户端声明不一致",
                status_code=409,
            )
        return FileUploadCompletionResult(file_object=file_object, sha256=file_object.sha256)
    if file_object.status != "pending_upload":
        raise AppError("FILE_UPLOAD_STATE_INVALID", "当前文件状态不允许完成上传", status_code=409)

    client = create_minio_client()
    object_info = await inspect_uploaded_object(client, file_object.bucket, file_object.object_key)
    actual_size = object_info.size
    actual_content_type = normalize_uploaded_object_content_type(object_info.content_type)
    expected_content_type = normalize_uploaded_object_content_type(file_object.content_type)

    if actual_size != file_object.size_bytes:
        raise AppError(
            "FILE_UPLOAD_SIZE_MISMATCH",
            "对象存储中的文件大小与上传意图不一致",
            status_code=409,
            details={"expected_size_bytes": file_object.size_bytes, "actual_size_bytes": actual_size},
        )
    if actual_content_type != expected_content_type:
        raise AppError(
            "FILE_UPLOAD_CONTENT_TYPE_MISMATCH",
            "对象存储中的文件类型与上传意图不一致",
            status_code=409,
            details={"expected_content_type": expected_content_type, "actual_content_type": actual_content_type},
        )

    sha256 = await asyncio.to_thread(calculate_minio_object_sha256, client, file_object.bucket, file_object.object_key)
    if expected_sha256 is not None and sha256.lower() != expected_sha256.lower():
        raise AppError(
            "FILE_UPLOAD_HASH_MISMATCH",
            "对象存储中的文件 hash 与客户端声明不一致",
            status_code=409,
        )

    verified_file = await repository.mark_upload_verified(file_object, sha256=sha256)
    return FileUploadCompletionResult(file_object=verified_file, sha256=sha256)
