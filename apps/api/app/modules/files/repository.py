# app/modules/files/repository.py
"""
文件元数据仓储

仓储层只处理 files 表，不直接调用 MinIO。对象上传、预签名 URL 和删除容错
由更高层的文件服务或具体业务服务协调。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.files.models import FileObject
from app.shared.time import utc_now


class FileRepository:
    """文件元数据数据库访问层。"""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def add(self, file_object: FileObject) -> FileObject:
        """新增文件元数据。"""

        self.session.add(file_object)
        await self.session.flush()
        return file_object

    async def get_by_id(self, file_id: int) -> FileObject | None:
        """按 file_id 查询文件元数据。"""

        return await self.session.scalar(select(FileObject).where(FileObject.id == file_id))

    async def mark_deleted(self, file_object: FileObject) -> FileObject:
        """
        标记文件已删除。

        这里不负责删除 MinIO 对象。旧系统已经出现过对象删除失败但数据库仍需清理的场景，
        后续业务服务会在物理删除失败时记录审计或补偿任务。
        """

        file_object.status = "deleted"
        file_object.deleted_at = utc_now()
        return file_object

    async def mark_upload_verified(self, file_object: FileObject, *, sha256: str) -> FileObject:
        """
        标记上传对象已经完成服务端复核。

        预签名 URL 只能证明客户端被允许写入某个对象 key，不能证明最终写入的对象
        与申请上传时声明的大小和类型一致。因此只有完成复核后，业务模块才能引用该文件。
        """

        file_object.status = "active"
        file_object.sha256 = sha256
        file_object.uploaded_at = utc_now()
        return file_object
