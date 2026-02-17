"""
Advanced logging configuration.

Colorized console output plus structured JSON logs with request correlation.
"""

import logging
import os
import socket
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import orjson

from app.core.settings import settings


correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id",
    default=None,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
HOSTNAME = socket.gethostname()

ANSI_RESET = "\033[0m"
ANSI_DIM = "\033[2m"
ANSI_BOLD = "\033[1m"

LEVEL_COLORS = {
    logging.DEBUG: "\033[38;5;246m",
    logging.INFO: "\033[38;5;39m",
    logging.WARNING: "\033[38;5;214m",
    logging.ERROR: "\033[38;5;196m",
    logging.CRITICAL: "\033[97;41m",
}
LOGGER_COLOR = "\033[38;5;81m"
SOURCE_COLOR = "\033[38;5;111m"
CORRELATION_COLOR = "\033[38;5;45m"
EXTRA_COLOR = "\033[38;5;120m"

_RESERVED_LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__.keys())
_INTERNAL_CONTEXT_FIELDS = {
    "correlation_id",
    "correlation_short",
    "source_path",
    "hostname",
    "environment",
    "app_name",
}


def _json_default(value: Any) -> str:
    return str(value)


def _relative_source_path(pathname: str) -> str:
    try:
        return Path(pathname).resolve().relative_to(PROJECT_ROOT).as_posix()
    except Exception:
        return Path(pathname).name


def _supports_color(stream: Any) -> bool:
    if os.getenv("NO_COLOR"):
        return False
    if os.getenv("FORCE_COLOR"):
        return True
    return bool(getattr(stream, "isatty", lambda: False)())


def _resolve_log_level(log_level: str) -> int:
    return getattr(logging, str(log_level).upper(), logging.INFO)


def _extract_extra_fields(record: logging.LogRecord) -> dict[str, Any]:
    extra_fields: dict[str, Any] = {}

    explicit_extra = getattr(record, "extra_fields", None)
    if isinstance(explicit_extra, dict):
        extra_fields.update(explicit_extra)

    for key, value in record.__dict__.items():
        if key in _RESERVED_LOG_RECORD_FIELDS:
            continue
        if key in _INTERNAL_CONTEXT_FIELDS or key in {"extra_fields", "message", "asctime"}:
            continue
        if key.startswith("_"):
            continue
        extra_fields[key] = value

    return extra_fields


def get_correlation_id() -> Optional[str]:
    """Get current correlation ID."""
    return correlation_id_var.get()


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set correlation ID for current context."""
    if correlation_id is None:
        correlation_id = str(uuid.uuid4())
    correlation_id_var.set(correlation_id)
    return correlation_id


class ContextFilter(logging.Filter):
    """Attach shared context fields to every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        correlation_id = get_correlation_id()
        record.correlation_id = correlation_id or "-"
        record.correlation_short = correlation_id[:8] if correlation_id else "-"
        record.source_path = _relative_source_path(record.pathname)
        record.hostname = HOSTNAME
        record.environment = settings.ENVIRONMENT.value
        record.app_name = settings.APP_NAME
        return True


class JSONFormatter(logging.Formatter):
    """Structured JSON formatter."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(
                record.created,
                tz=timezone.utc,
            ).isoformat(),
            "app": getattr(record, "app_name", settings.APP_NAME),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "source": getattr(record, "source_path", _relative_source_path(record.pathname)),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
            "process": record.process,
            "thread": record.threadName,
            "hostname": getattr(record, "hostname", HOSTNAME),
            "environment": getattr(record, "environment", settings.ENVIRONMENT.value),
            "correlation_id": getattr(record, "correlation_id", "-"),
        }

        extra_fields = _extract_extra_fields(record)
        if extra_fields:
            payload["extra"] = extra_fields

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        if record.stack_info:
            payload["stack"] = self.formatStack(record.stack_info)

        return orjson.dumps(payload, default=_json_default).decode("utf-8")


class DetailedFormatter(logging.Formatter):
    """Detailed console formatter with optional ANSI colors."""

    def __init__(self, use_color: bool = True) -> None:
        super().__init__(datefmt="%Y-%m-%d %H:%M:%S")
        self.use_color = use_color

    def _paint(self, text: str, color: str = "", bold: bool = False) -> str:
        if not self.use_color:
            return text
        style = ANSI_BOLD if bold else ""
        return f"{style}{color}{text}{ANSI_RESET}"

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        level = f"{record.levelname:<8}"
        source = f"{getattr(record, 'source_path', _relative_source_path(record.pathname))}:{record.lineno}"
        correlation = getattr(record, "correlation_short", "-")
        app_env = (
            f" [app={getattr(record, 'app_name', settings.APP_NAME)} "
            f"env={getattr(record, 'environment', settings.ENVIRONMENT.value)}]"
        )

        line = (
            f"{self._paint(timestamp, ANSI_DIM)} "
            f"{self._paint(level, LEVEL_COLORS.get(record.levelno, ''), bold=record.levelno >= logging.ERROR)} "
            f"{self._paint(record.name, LOGGER_COLOR)} "
            f"{self._paint(source, SOURCE_COLOR)} "
            f"{self._paint(f'cid={correlation}', CORRELATION_COLOR)} "
            f"{record.getMessage()}"
            f"{self._paint(app_env, ANSI_DIM)}"
            f"{self._paint(f' [pid={record.process} thread={record.threadName}]', ANSI_DIM)}"
        )

        extra_fields = _extract_extra_fields(record)
        if extra_fields:
            encoded_extra = orjson.dumps(
                extra_fields,
                default=_json_default,
            ).decode("utf-8")
            line = f"{line} {self._paint('|', ANSI_DIM)} {self._paint(encoded_extra, EXTRA_COLOR)}"

        if record.exc_info:
            line = f"{line}\n{self.formatException(record.exc_info)}"
        if record.stack_info:
            line = f"{line}\n{self.formatStack(record.stack_info)}"

        return line


def setup_logging() -> None:
    """Configure application logging."""
    log_level = _resolve_log_level(settings.LOG_LEVEL)
    log_format = str(settings.LOG_FORMAT).lower()

    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)

    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    context_filter = ContextFilter()

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.addFilter(context_filter)

    if log_format == "json" and settings.is_development and _supports_color(sys.stdout):
        console_handler.setFormatter(DetailedFormatter(use_color=True))
    elif log_format == "json":
        console_handler.setFormatter(JSONFormatter())
    elif log_format in {"plain", "standard", "text"}:
        console_handler.setFormatter(DetailedFormatter(use_color=False))
    else:
        console_handler.setFormatter(DetailedFormatter(use_color=_supports_color(sys.stdout)))

    root_logger.addHandler(console_handler)

    if settings.LOG_FILE:
        file_handler = logging.FileHandler(settings.LOG_FILE, encoding="utf-8")
        file_handler.setLevel(log_level)
        file_handler.addFilter(context_filter)
        file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    logging.captureWarnings(True)

    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(log_level)
    logging.getLogger("sqlalchemy.engine").setLevel(
        logging.INFO if settings.DATABASE_ECHO else logging.WARNING
    )


def get_logger(name: str) -> logging.Logger:
    """Get logger instance."""
    return logging.getLogger(name)


class LoggerAdapter(logging.LoggerAdapter):
    """Logger adapter with extra fields support."""

    def process(
        self,
        msg: str,
        kwargs: dict[str, Any],
    ) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra")
        if not isinstance(extra, dict):
            extra = {}

        existing_extra_fields = extra.get("extra_fields", {})
        if not isinstance(existing_extra_fields, dict):
            existing_extra_fields = {}

        extra["extra_fields"] = {**self.extra, **existing_extra_fields}
        kwargs["extra"] = extra
        return msg, kwargs


def get_context_logger(name: str, **context: Any) -> LoggerAdapter:
    """Get logger with context fields."""
    return LoggerAdapter(logging.getLogger(name), context)


setup_logging()
logger = get_logger("app")
