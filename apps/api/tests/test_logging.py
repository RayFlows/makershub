# tests/test_logging.py
"""
运行日志基础设施测试

运行日志用于定位服务异常和请求链路，必须按用途分流并具备明确保留策略。
"""

from __future__ import annotations

import logging as stdlib_logging
from pathlib import Path

from app.core.config.settings import get_settings
from app.core.logging import logger, setup_logging
from app.core.logging.setup import LOG_CATEGORY_EXTRA_KEY, REQUEST_LOG_CATEGORY


def read_log(path: Path) -> str:
    """读取测试日志文件，文件未创建时返回空字符串。"""

    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def test_logging_writes_runtime_error_request_and_debug_files(tmp_path, monkeypatch) -> None:
    """日志系统应该把运行、错误、请求和 debug 明细写入不同文件。"""

    monkeypatch.setenv("APP_ENV", "local")
    monkeypatch.setenv("LOG_DIR", str(tmp_path))
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("LOG_FILE_ENABLED", "true")
    monkeypatch.setenv("LOG_CONSOLE_ENABLED", "false")
    monkeypatch.setenv("LOG_ENQUEUE", "false")
    monkeypatch.setenv("LOG_DEBUG_FILE_ENABLED", "true")
    get_settings.cache_clear()

    try:
        setup_logging()

        request_logger = logger.bind(**{LOG_CATEGORY_EXTRA_KEY: REQUEST_LOG_CATEGORY})
        logger.info("runtime info")
        logger.warning("runtime warning")
        logger.debug("debug detail")
        logger.error("runtime error")
        request_logger.info("request info")
        request_logger.error("request error")
        stdlib_logging.getLogger("uvicorn.access").info("uvicorn access")

        app_log = read_log(tmp_path / "app.log")
        error_log = read_log(tmp_path / "error.log")
        request_log = read_log(tmp_path / "request.log")
        debug_log = read_log(tmp_path / "debug.log")

        assert "runtime info" in app_log
        assert "runtime warning" in app_log
        assert "runtime error" not in app_log
        assert "debug detail" not in app_log
        assert "request info" not in app_log
        assert "uvicorn access" not in app_log

        assert "runtime error" in error_log
        assert "request error" in error_log
        assert "runtime info" not in error_log

        assert "request info" in request_log
        assert "request error" in request_log
        assert "uvicorn access" in request_log
        assert "runtime info" not in request_log

        assert "debug detail" in debug_log
        assert "runtime info" not in debug_log
        assert "runtime error" not in debug_log
    finally:
        logger.remove()
        get_settings.cache_clear()
