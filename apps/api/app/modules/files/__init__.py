# app/modules/files/__init__.py
"""
文件领域导出

文件模块负责 MinIO 对象对应的元数据、对象 key 生成和文件状态管理。
业务模块只保存 file_id，不直接把对象存储路径散落到各自的数据表里。
"""

from app.modules.files.models import FileObject
from app.modules.files.service import FileMetadataInput, build_object_key, register_file_metadata

__all__ = ["FileMetadataInput", "FileObject", "build_object_key", "register_file_metadata"]

