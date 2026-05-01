# app/core/logging.py
"""
后端日志配置

本文件负责统一配置 Loguru、文件轮转和标准 logging 接入。
旧后端已经证明日志对排查微信登录、上传、审核和后台操作非常关键；新项目继续保留
“控制台 + 文件轮转 + request_id 串联”的能力，但避免在请求日志中记录请求体，
防止密码、token、验证码等敏感数据进入日志文件。
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from pathlib import Path

from loguru import logger

from app.core.config.settings import get_settings


class InterceptHandler(stdlib_logging.Handler):
    """
    标准 logging 到 Loguru 的桥接器。

    FastAPI、Uvicorn、SQLAlchemy 和部分基础设施库仍然使用标准 logging。
    统一桥接后，验证码 log 模式、框架日志和业务日志可以进入同一套 sink。
    """

    def emit(self, record: stdlib_logging.LogRecord) -> None:
        """把标准 logging 记录转交给 Loguru。"""

        try:
            level: str | int = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


def setup_logging() -> None:
    """
    初始化后端日志系统。

    该函数可以被测试或 reload 进程重复调用；每次会先清理旧 sink，避免日志重复输出。
    """

    settings = get_settings()
    level = settings.log_level.upper()

    logger.remove()
    logger.configure(extra={"request_id": "-"})

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[request_id]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]} | "
        "{name}:{function}:{line} - {message}"
    )

    logger.add(
        sys.stdout,
        level=level,
        format=console_format,
        enqueue=settings.log_enqueue,
        backtrace=settings.app_env != "production",
        diagnose=settings.app_env != "production",
    )

    if settings.log_file_enabled:
        log_dir = Path(settings.log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)
        logger.add(
            log_dir / settings.log_file,
            level=level,
            format=file_format,
            rotation=settings.log_rotation,
            retention=settings.log_retention,
            compression=settings.log_compression or None,
            encoding="utf-8",
            enqueue=settings.log_enqueue,
            backtrace=settings.app_env != "production",
            diagnose=False,
        )

    # 标准 logging 统一进入 Loguru，避免同一进程里出现多套日志格式。
    stdlib_logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        stdlib_logger = stdlib_logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = True
