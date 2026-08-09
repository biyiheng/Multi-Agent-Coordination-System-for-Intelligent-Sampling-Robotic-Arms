"""
Logging configuration module for the intelligent sampling robotic arm system.

Provides colored console logging with file rotation, supporting multiple log levels
and structured output including timestamp, level, module name, and message.
"""

import json
import os
import sys
import logging
import logging.handlers
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


# Color codes for terminal output
class LogColors:
    """ANSI color codes for log level formatting."""

    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"

    COLORS = {
        "DEBUG": "\033[36m",      # Cyan
        "INFO": "\033[32m",       # Green
        "WARNING": "\033[33m",    # Yellow
        "ERROR": "\033[31m",      # Red
        "CRITICAL": "\033[35m",   # Magenta
    }


class ColoredFormatter(logging.Formatter):
    """Custom formatter adding ANSI color codes to log level names for console output."""

    LEVEL_COLORS = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[35m",   # Magenta
    }

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record with colorized level name."""
        level_color = self.LEVEL_COLORS.get(record.levelno, "")
        original_levelname = record.levelname
        if level_color:
            record.levelname = f"{level_color}{record.levelname:<8}{LogColors.RESET}"
        else:
            record.levelname = f"{record.levelname:<8}"

        result = super().format(record)
        record.levelname = original_levelname
        return result


class PlainFormatter(logging.Formatter):
    """Standard formatter without color codes for file output."""

    pass


# 标准 logging 内部属性, 不写入 JSON 结构化输出
_STD_LOG_ATTRS = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}


class JsonFormatter(logging.Formatter):
    """Structured JSON log formatter.

    每行输出一个 JSON 对象, 便于对接日志采集系统 (filebeat/fluentd/vector 等)。
    除标准字段外, 调用方通过 `extra={...}` 传入的自定义字段会自动并入顶层。

    Example:
        logger.info("grasp ok", extra={"event": "grasp", "travel_mm": 274.1})
    """

    def __init__(self, ensure_ascii: bool = False) -> None:
        super().__init__()
        self._ensure_ascii = ensure_ascii

    def format(self, record: logging.LogRecord) -> str:
        # ISO8601 时间戳 (UTC) + 本地毫秒
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat()

        entry: dict = {
            "ts": ts,
            "level": record.levelname,
            "logger": record.name,
            "file": record.filename,
            "line": record.lineno,
            "func": record.funcName,
            "msg": record.getMessage(),
        }

        # 异常堆栈
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)

        # 并入 extra 自定义字段 (排除内部属性)
        for key, value in record.__dict__.items():
            if key not in _STD_LOG_ATTRS and not key.startswith("_"):
                entry[key] = value

        return json.dumps(entry, ensure_ascii=self._ensure_ascii,
                          default=str)


def setup_logger(
    name: str = "rpi_control",
    level: str = "INFO",
    log_dir: Optional[str] = None,
    log_to_console: bool = True,
    log_to_file: bool = True,
    max_bytes: int = 10 * 1024 * 1024,  # 10 MB
    backup_count: int = 5,
    log_format: Optional[str] = None,
) -> logging.Logger:
    """
    Set up and configure a logger with console and file handlers.

    Args:
        name: Logger name.
        level: Log level string (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        log_dir: Directory for log files. Defaults to 'logs/' relative to project root.
        log_to_console: Whether to enable console output.
        log_to_file: Whether to enable rotating file output.
        max_bytes: Maximum size of each log file before rotation.
        backup_count: Number of backup log files to retain.
        log_format: "text" (human-readable, default) or "json" (structured, one
                    JSON object per line). 未指定时读取环境变量 RPI_LOG_FORMAT.

    Returns:
        Configured logging.Logger instance.
    """
    # 格式: 优先显式参数, 其次环境变量 RPI_LOG_FORMAT, 默认 text
    if log_format is None:
        log_format = os.environ.get("RPI_LOG_FORMAT", "text").lower()
    json_mode = log_format in ("json", "structured")

    logger = logging.getLogger(name)

    # Prevent duplicate handlers when called multiple times
    if logger.hasHandlers():
        logger.handlers.clear()

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(numeric_level)

    # Console handler (JSON 模式不启用彩色, 保持纯净单行)
    if log_to_console:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(numeric_level)
        if json_mode:
            console_format = JsonFormatter()
        else:
            console_format = ColoredFormatter(
                fmt="%(asctime)s.%(msecs)03d | %(levelname)s | %(name)s | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

    # File handler with rotation
    if log_to_file:
        if log_dir is None:
            log_dir = str(Path(__file__).resolve().parent.parent / "logs")
        log_path = Path(log_dir)
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = logging.handlers.RotatingFileHandler(
            filename=log_path / f"{name}.log",
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(numeric_level)
        if json_mode:
            file_format = JsonFormatter()
        else:
            file_format = PlainFormatter(
                fmt="%(asctime)s.%(msecs)03d | %(levelname)-8s | %(name)s | %(filename)s:%(lineno)d | %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get a child logger with the given name.

    Args:
        name: The logger name, typically __name__ of the calling module.

    Returns:
        A logging.Logger instance.
    """
    return logging.getLogger(f"rpi_control.{name}")


# Default module-level logger
logger = get_logger(__name__)