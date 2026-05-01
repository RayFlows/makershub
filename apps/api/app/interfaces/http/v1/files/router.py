# app/interfaces/http/v1/files/router.py
"""
文件 V1 路由

本路由提供统一上传入口。客户端先向后端申请上传意图，后端校验用途、大小和文件类型，
登记文件元数据后返回短期预签名 URL。业务模块后续只引用 file_id，不直接操作 MinIO。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_session
from app.interfaces.http.dependencies import CurrentUser, get_current_user
from app.interfaces.http.v1.files.schemas import CreateUploadIntentRequest, UploadIntentResponse
from app.modules.files.service import FileUploadIntentInput, create_file_upload_intent
from app.shared.request_context import get_request_id
from app.shared.responses import success_response

router = APIRouter(prefix="/files")


@router.post("/upload-intents")
async def create_upload_intent(
    payload: CreateUploadIntentRequest,
    request: Request,
    current: CurrentUser = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
):
    """
    创建文件上传意图。

    返回的 `upload_url` 是短期 PUT URL；客户端上传完成后，具体业务模块再引用 `file_id`
    完成项目材料、头像或资源附件等业务绑定。
    """

    result = await create_file_upload_intent(
        session,
        owner_user_id=current.user.id,
        payload=FileUploadIntentInput(
            purpose=payload.purpose,
            original_filename=payload.original_filename,
            content_type=payload.content_type,
            size_bytes=payload.size_bytes,
        ),
    )
    await session.commit()
    response = UploadIntentResponse(
        file_id=result.file_object.id,
        bucket=result.file_object.bucket,
        object_key=result.file_object.object_key,
        upload_url=result.upload_url,
        method=result.method,
        expires_in=result.expires_in,
        status=result.file_object.status,
        content_type=result.file_object.content_type,
        size_bytes=result.file_object.size_bytes,
    )
    return success_response(response.model_dump(), request_id=get_request_id(request))
