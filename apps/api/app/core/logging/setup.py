# app/core/logging/setup.py
"""
后端日志配置

本文件负责统一配置 Loguru、文件分流、轮转保留和标准 logging 接入。
旧后端已经证明日志对排查微信登录、上传、审核和后台操作非常关键；新项目继续保留
“控制台 + 分级文件 + request_id 串联”的能力，但避免在请求日志中记录请求体，
防止密码、token、验证码等敏感数据进入日志文件。生产环境不默认写 debug 文件，
避免服务长期运行后低价值日志无限堆积。
"""

from __future__ import annotations

import logging as stdlib_logging
import sys
from collections.abc import Callable
from pathlib import Path

from loguru import logger

from app.core.config.settings import get_settings

LOG_CATEGORY_EXTRA_KEY = "log_category"
REQUEST_LOG_CATEGORY = "request"
APPLICATION_LOG_LEVELS = {"INFO", "SUCCESS", "WARNING"}


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

        # Uvicorn 访问日志也归入 request.log，避免框架访问日志重新污染 app.log。
        target_logger = logger
        if record.name == "uvicorn.access":
            target_logger = logger.bind(**{LOG_CATEGORY_EXTRA_KEY: REQUEST_LOG_CATEGORY})

        target_logger.opt(exception=record.exc_info, depth=6).log(level, record.getMessage())


def has_category(record: dict, category: str) -> bool:
    """判断日志记录是否属于指定分类。"""

    return record["extra"].get(LOG_CATEGORY_EXTRA_KEY) == category


def is_application_log(record: dict) -> bool:
    """
    判断是否写入综合运行日志。

    app.log 只保留普通运行信息和 warning；请求访问、debug 明细和 error 事故日志
    分别进入 request.log、debug.log 和 error.log，避免一个文件越跑越杂。
    """

    if has_category(record, REQUEST_LOG_CATEGORY):
        return False
    return record["level"].name in APPLICATION_LOG_LEVELS


def level_at_least(level_name: str) -> Callable[[dict], bool]:
    """
    构造最低等级过滤器。

    Args:
        level_name: Loguru 等级名称。
    """

    threshold = logger.level(level_name).no

    def filter_record(record: dict) -> bool:
        return record["level"].no >= threshold

    return filter_record


def exact_level(level_name: str) -> Callable[[dict], bool]:
    """
    构造精确等级过滤器。

    主要用于 debug 文件，只写 DEBUG，避免和 app.log/info/error 大量重复。
    """

    target = logger.level(level_name).no

    def filter_record(record: dict) -> bool:
        return record["level"].no == target

    return filter_record


def add_file_sink(
    *,
    path: Path,
    level: str,
    file_format: str,
    rotation: str,
    retention: str,
    compression: str | None,
    enqueue: bool,
    log_filter: Callable[[dict], bool],
    backtrace: bool,
) -> None:
    """注册一个文件日志 sink。"""

    logger.add(
        path,
        level=level,
        format=file_format,
        rotation=rotation,
        retention=retention,
        compression=compression,
        encoding="utf-8",
        enqueue=enqueue,
        backtrace=backtrace,
        diagnose=False,
        filter=log_filter,
    )


def setup_logging() -> None:
    """
    初始化后端日志系统。

    该函数可以被测试或 reload 进程重复调用；每次会先清理旧 sink，避免日志重复输出。
    """

    settings = get_settings()
    level = settings.log_level.upper()

    logger.remove()
    logger.configure(extra={"request_id": "-", LOG_CATEGORY_EXTRA_KEY: "app"})

    console_format = (
        "<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{extra[request_id]}</cyan> | "
        "<cyan>{extra[log_category]}</cyan> | "
        "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
        "<level>{message}</level>"
    )
    file_format = (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {extra[request_id]} | "
        "{extra[log_category]} | "
        "{name}:{function}:{line} - {message}"
    )

    if settings.log_console_enabled:
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
        compression = settings.log_compression or None
        backtrace = settings.app_env != "production"

        # 综合运行日志：普通 INFO/SUCCESS/WARNING，排除请求、debug 和 error 分流日志。
        add_file_sink(
            path=log_dir / settings.log_app_file,
            level=level,
            file_format=file_format,
            rotation=settings.log_rotation,
            retention=settings.log_retention,
            compression=compression,
            enqueue=settings.log_enqueue,
            log_filter=is_application_log,
            backtrace=backtrace,
        )
        # 错误日志保留更久，包含所有 ERROR/CRITICAL，方便线上事故复盘。
        add_file_sink(
            path=log_dir / settings.log_error_file,
            level="ERROR",
            file_format=file_format,
            rotation=settings.log_rotation,
            retention=settings.log_error_retention,
            compression=compression,
            enqueue=settings.log_enqueue,
            log_filter=level_at_least("ERROR"),
            backtrace=backtrace,
        )
        # 请求访问日志单独保存，避免 app.log 被高频请求刷屏。
        add_file_sink(
            path=log_dir / settings.log_request_file,
            level="INFO",
            file_format=file_format,
            rotation=settings.log_rotation,
            retention=settings.log_request_retention,
            compression=compression,
            enqueue=settings.log_enqueue,
            log_filter=lambda record: has_category(record, REQUEST_LOG_CATEGORY),
            backtrace=backtrace,
        )
        if settings.should_write_debug_log_file:
            add_file_sink(
                path=log_dir / settings.log_debug_file,
                level="DEBUG",
                file_format=file_format,
                rotation=settings.log_rotation,
                retention=settings.log_debug_retention,
                compression=compression,
                enqueue=settings.log_enqueue,
                log_filter=exact_level("DEBUG"),
                backtrace=backtrace,
            )

    # 标准 logging 统一进入 Loguru，避免同一进程里出现多套日志格式。
    stdlib_logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)
    for logger_name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        stdlib_logger = stdlib_logging.getLogger(logger_name)
        stdlib_logger.handlers.clear()
        stdlib_logger.propagate = True
