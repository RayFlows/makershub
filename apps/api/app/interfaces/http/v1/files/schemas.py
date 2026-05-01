# app/interfaces/http/v1/files/schemas.py
"""
文件接口请求与响应模型

接口层只描述 HTTP 契约。上传用途、安全策略、对象 key 生成和文件元数据登记
由 files 服务层负责。
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class CreateUploadIntentRequest(BaseModel):
    """创建上传意图请求。"""

    purpose: str = Field(..., min_length=1, max_length=64)
    original_filename: str = Field(..., min_length=1, max_length=255)
    content_type: str = Field(..., min_length=3, max_length=128)
    size_bytes: int = Field(..., gt=0)


class UploadIntentResponse(BaseModel):
    """创建上传意图响应。"""

    file_id: int
    bucket: str
    object_key: str
    upload_url: str
    method: str
    expires_in: int
    status: str
    content_type: str | None
    size_bytes: int


class CompleteUploadRequest(BaseModel):
    """完成上传请求。"""

    sha256: str | None = Field(None, pattern=r"^[a-fA-F0-9]{64}$")


class CompletedUploadResponse(BaseModel):
    """完成上传响应。"""

    file_id: int
    bucket: str
    object_key: str
    status: str
    content_type: str | None
    size_bytes: int
    sha256: str
