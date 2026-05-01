# app/core/logging/__init__.py
"""
日志基础设施导出

日志配置按包组织，避免核心目录里同时出现 `logging.py` 和 `logging/` 两种结构。
业务代码只从这里导入 `logger` 和 `setup_logging`，不要直接关心 Loguru sink 细节。
"""

from loguru import logger

from app.core.logging.setup import setup_logging

__all__ = ["logger", "setup_logging"]
