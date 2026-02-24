"""
InfinityAI – Production-grade logging
=====================================
Structured JSON (file) + human-readable colored console.
Correlation IDs, sanitization, request/response helpers, RequestTimer.

Usage:
    from app.core.logger import get_logger, log_api_request, log_api_response

    logger = get_logger(__name__)
    logger.info("message")
"""

import logging
import logging.handlers
import json
import os
import time
import traceback
import uuid
import contextvars
from datetime import datetime, timezone
from typing import Any, Dict, Optional

# ---------------------------------------------------------------------------
# Correlation ID (request tracing)
# ---------------------------------------------------------------------------
_correlation_id: contextvars.ContextVar[str] = contextvars.ContextVar(
    "correlation_id", default=""
)


def set_correlation_id(cid: Optional[str] = None) -> str:
    """Set or generate a correlation ID for the current context."""
    cid = cid or uuid.uuid4().hex[:12]
    _correlation_id.set(cid)
    return cid


def get_correlation_id() -> str:
    return _correlation_id.get("")


# ---------------------------------------------------------------------------
# Sensitive-field sanitization
# ---------------------------------------------------------------------------
_SENSITIVE_KEYS = frozenset({
    "authorization", "password", "secret", "token", "api_key", "apikey",
    "access_token", "refresh_token", "credential", "private_key",
    "aws_secret_access_key", "client_secret",
})


def _sanitize(data: Any, depth: int = 0) -> Any:
    """Recursively redact values whose keys look sensitive."""
    if depth > 8:
        return "..."
    if isinstance(data, dict):
        return {
            k: ("***REDACTED***" if k.lower() in _SENSITIVE_KEYS else _sanitize(v, depth + 1))
            for k, v in data.items()
        }
    if isinstance(data, (list, tuple)):
        return [_sanitize(item, depth + 1) for item in data]
    return data


# ---------------------------------------------------------------------------
# JSON formatter (file handler)
# ---------------------------------------------------------------------------
class JSONFormatter(logging.Formatter):
    """Emit each log record as a single JSON line."""

    def format(self, record: logging.LogRecord) -> str:
        log_entry: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        cid = get_correlation_id()
        if cid:
            log_entry["correlation_id"] = cid

        for key in (
            "event", "method", "path", "status_code", "duration_ms",
            "provider", "recipient", "template", "error", "detail",
            "request_body", "response_body", "headers", "message_id",
        ):
            val = getattr(record, key, None)
            if val is not None:
                log_entry[key] = val

        if record.exc_info and record.exc_info[0] is not None:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


# ---------------------------------------------------------------------------
# Colored console formatter
# ---------------------------------------------------------------------------
_COLORS = {
    "DEBUG": "\033[36m",
    "INFO": "\033[32m",
    "WARNING": "\033[33m",
    "ERROR": "\033[31m",
    "CRITICAL": "\033[1;31m",
}
_RESET = "\033[0m"
_DIM = "\033[2m"


class ColoredConsoleFormatter(logging.Formatter):
    """Human-readable colored output for the terminal."""

    def format(self, record: logging.LogRecord) -> str:
        color = _COLORS.get(record.levelname, "")
        cid = get_correlation_id()
        cid_str = f" [{cid}]" if cid else ""

        ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        header = (
            f"{_DIM}{ts}{_RESET} "
            f"{color}{record.levelname:<8}{_RESET} "
            f"{_DIM}{record.name}{_RESET}{cid_str}"
        )
        msg = record.getMessage()

        extras = []
        for key in ("event", "method", "path", "status_code", "duration_ms", "provider"):
            val = getattr(record, key, None)
            if val is not None:
                extras.append(f"{key}={val}")
        extra_str = f"  {_DIM}({', '.join(extras)}){_RESET}" if extras else ""

        detail = getattr(record, "detail", None)
        detail_str = f"\n  {_DIM}detail: {detail}{_RESET}" if detail else ""
        error = getattr(record, "error", None)
        error_str = f"\n  {color}error: {error}{_RESET}" if error else ""

        exc_str = ""
        if record.exc_info and record.exc_info[0] is not None:
            exc_str = f"\n{self.formatException(record.exc_info)}"

        return f"{header} {msg}{extra_str}{detail_str}{error_str}{exc_str}"


# ---------------------------------------------------------------------------
# Logger factory
# ---------------------------------------------------------------------------
_LOG_DIR = os.getenv("LOG_DIR", os.path.join(os.path.dirname(__file__), "..", "logs"))
_LOG_FILE = os.getenv("LOG_FILE", "app.log")
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_MAX_BYTES = int(os.getenv("LOG_MAX_BYTES", str(10 * 1024 * 1024)))
_LOG_BACKUP_COUNT = int(os.getenv("LOG_BACKUP_COUNT", "5"))
_ENABLE_FILE_LOG = os.getenv("LOG_TO_FILE", "1").strip().lower() in ("1", "true", "yes")

_initialized = False


def _ensure_log_dir() -> str:
    path = os.path.abspath(_LOG_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _setup_root_once() -> None:
    global _initialized
    if _initialized:
        return
    _initialized = True

    root = logging.getLogger()
    root.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))

    console = logging.StreamHandler()
    console.setFormatter(ColoredConsoleFormatter())
    console.setLevel(getattr(logging, _LOG_LEVEL, logging.INFO))
    root.addHandler(console)

    if _ENABLE_FILE_LOG:
        try:
            log_dir = _ensure_log_dir()
            fh = logging.handlers.RotatingFileHandler(
                os.path.join(log_dir, _LOG_FILE),
                maxBytes=_LOG_MAX_BYTES,
                backupCount=_LOG_BACKUP_COUNT,
                encoding="utf-8",
            )
            fh.setFormatter(JSONFormatter())
            fh.setLevel(logging.DEBUG)
            root.addHandler(fh)
        except OSError:
            pass


def get_logger(name: str) -> logging.Logger:
    """Return a named logger. First call configures root with console + file handlers."""
    _setup_root_once()
    return logging.getLogger(name)


# Module-level logger for convenience imports
logger = get_logger("app")


# ---------------------------------------------------------------------------
# Request timer
# ---------------------------------------------------------------------------
class RequestTimer:
    """Measure elapsed time for a block of code."""

    def __init__(self) -> None:
        self.start: float = 0.0
        self.end: float = 0.0
        self.duration_ms: float = 0.0

    def __enter__(self) -> "RequestTimer":
        self.start = time.perf_counter()
        return self

    def __exit__(self, *exc: Any) -> None:
        self.end = time.perf_counter()
        self.duration_ms = round((self.end - self.start) * 1000, 2)


# ---------------------------------------------------------------------------
# Structured logging helpers
# ---------------------------------------------------------------------------
def log_api_request(
    logger: logging.Logger,
    method: str,
    path: str,
    body: Any = None,
    headers: Optional[Dict[str, str]] = None,
    query_params: Optional[Dict[str, str]] = None,
    correlation_id: Optional[str] = None,
) -> str:
    """Log an incoming API request. Returns the correlation_id used."""
    cid = set_correlation_id(correlation_id)
    safe_headers = _sanitize(headers) if headers else None
    safe_body = _sanitize(body) if body is not None else None

    logger.info(
        f"API Request: {method} {path}",
        extra={
            "event": "api_request",
            "method": method,
            "path": path,
            "headers": safe_headers,
            "request_body": safe_body,
            "detail": query_params if query_params else None,
        },
    )
    return cid


def log_api_response(
    logger: logging.Logger,
    method: str,
    path: str,
    status_code: int,
    body: Any = None,
    duration_ms: Optional[float] = None,
) -> None:
    """Log an API response."""
    level = (
        logging.INFO if status_code < 400
        else logging.WARNING if status_code < 500
        else logging.ERROR
    )
    safe_body = _sanitize(body) if body is not None else None

    logger.log(
        level,
        f"API Response: {method} {path} -> {status_code}",
        extra={
            "event": "api_response",
            "method": method,
            "path": path,
            "status_code": status_code,
            "response_body": safe_body,
            "duration_ms": duration_ms,
        },
    )


def log_exception(
    logger: logging.Logger,
    message: str,
    exc: Optional[BaseException] = None,
    context: Optional[Dict[str, Any]] = None,
) -> None:
    """Log an exception with full traceback and optional context."""
    tb = traceback.format_exception(type(exc), exc, exc.__traceback__) if exc else None
    logger.error(
        message,
        extra={
            "event": "exception",
            "error": str(exc) if exc else None,
            "detail": {"traceback": "".join(tb) if tb else None, **(context or {})},
        },
    )


# ---------------------------------------------------------------------------
# Backward compatibility: lambda_handler and root logger
# ---------------------------------------------------------------------------
def lambda_handler(event: Dict[str, Any], context: Any = None, log_level: Optional[str] = None) -> Dict[str, Any]:
    """
    Lambda-style logger. Accepts event with 'message' and optional 'level' / 'extra'.
    """
    lgr = get_logger("lambda")
    level_str = (log_level or event.get("level", "INFO")).upper()
    message = event.get("message", "")
    extra = event.get("extra", {})
    level = getattr(logging, level_str, logging.INFO)
    if extra:
        lgr.log(level, f"{message} | Extra: {json.dumps(extra)}")
    else:
        lgr.log(level, message)
    return {"statusCode": 200, "body": json.dumps({"logged": True, "level": level_str, "message": message})}
