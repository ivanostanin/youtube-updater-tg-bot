import logging
import logging.handlers
import os
import sys
import uuid
from collections.abc import Mapping, MutableMapping
from pathlib import Path
from threading import Lock
from typing import Any

from pythonjsonlogger import json

from .config import settings


class UnbufferedStreamHandler(logging.StreamHandler):
    """Stream handler that forces immediate flushing."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


_logging_lock = Lock()
_logging_configured = False
CONTEXT_KEYS = (
    "chat_id",
    "chat_type",
    "user_id",
    "channel_id",
    "subscription_id",
    "video_id",
    "operation",
    "request_id",
)
META_PREFIX = "meta_"
MAX_LABEL_LENGTH = 60
MAX_OPERATION_LENGTH = 48
MAX_REQUEST_ID_LENGTH = 24


def _is_logging_configured() -> bool:
    return _logging_configured


def setup_logging() -> logging.Logger:
    """Configure logging for the application."""
    global _logging_configured

    if _is_logging_configured():
        return logging.getLogger(__name__)

    with _logging_lock:
        if _is_logging_configured():
            return logging.getLogger(__name__)

        log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

        # Create logs directory if it doesn't exist
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)

        # Determine if JSON logging is enabled via environment variable
        use_json_logging = os.getenv("JSON_LOGGING", "false").lower() in ("true", "1", "yes")

        # Create formatters
        if use_json_logging:
            # JSON formatter with required context fields
            json_formatter = json.JsonFormatter(
                "%(timestamp)s %(level)s %(name)s %(message)s "
                "%(user_id)s %(chat_id)s %(channel_id)s "
                "%(operation)s %(request_id)s",
                rename_fields={"levelname": "level", "asctime": "timestamp"},
                datefmt="%Y-%m-%dT%H:%M:%S",
            )
            console_formatter = json_formatter
            file_formatter = json_formatter
        else:
            # Traditional text formatter
            text_formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            console_formatter = text_formatter  # type: ignore[assignment]
            file_formatter = text_formatter  # type: ignore[assignment]

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear any existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create console handler with immediate flushing
        console_handler = UnbufferedStreamHandler(sys.stdout)
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(log_level)

        # Create file handler
        file_handler = logging.FileHandler(logs_dir / "bot.log", mode="a")
        file_handler.setFormatter(file_formatter)
        file_handler.setLevel(log_level)

        # Add our handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        # Set specific loggers
        logging.getLogger("aiosqlite").setLevel(logging.INFO)
        logging.getLogger("telegram").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.INFO)
        logging.getLogger("httpcore.http11").setLevel(logging.INFO)
        logging.getLogger("httpcore.connection").setLevel(logging.INFO)
        logging.getLogger("sqlalchemy.engine.Engine").setLevel(
            logging.WARNING
        )  # Break the glass in case of emergency

        # Configure asyncio logger to be more verbose in debug mode
        if log_level <= logging.DEBUG:
            logging.getLogger("asyncio").setLevel(logging.DEBUG)

        # Ensure SQLAlchemy echoes propagate through our handlers only once.
        engine_logger = logging.getLogger("sqlalchemy.engine")
        engine_logger.handlers.clear()
        engine_logger.propagate = True
        if log_level <= logging.DEBUG:
            engine_logger.setLevel(logging.INFO)
        else:
            engine_logger.setLevel(logging.WARNING)

        # Test log message
        logger = logging.getLogger(__name__)
        logger.info("Logging system initialized successfully")

        _logging_configured = True
        return logger


def sanitize_label(value: str | None, *, max_length: int = MAX_LABEL_LENGTH) -> str | None:
    """Return a human-readable label trimmed for safe logging."""
    if value is None:
        return None
    text = " ".join(str(value).split())
    if not text:
        return None
    if len(text) <= max_length:
        return text
    return f"{text[: max_length - 3]}..."


def _should_include_context(key: str) -> bool:
    return key in CONTEXT_KEYS or key.startswith(META_PREFIX)


def _sanitize_context_value(key: str, value: Any) -> str | int | float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value

    text = str(value).strip()
    if not text:
        return None

    if key == "operation" and len(text) > MAX_OPERATION_LENGTH:
        return f"{text[: MAX_OPERATION_LENGTH - 3]}..."
    if key == "request_id" and len(text) > MAX_REQUEST_ID_LENGTH:
        return text[:MAX_REQUEST_ID_LENGTH]
    if key.startswith(META_PREFIX):
        return sanitize_label(text)
    return text


def log_context(**kwargs: Any) -> dict[str, str | int | float]:
    """Build a sanitized key/value mapping for log adapters."""
    sanitized: dict[str, str | int | float] = {}
    for key, value in kwargs.items():
        if not _should_include_context(key):
            continue
        normalized = _sanitize_context_value(key, value)
        if normalized is None:
            continue
        sanitized[key] = normalized
    return sanitized


class ContextLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that formats and persists standardized context."""

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        context: dict[str, Any] = {}
        context.update(self.extra or {})
        extra = kwargs.pop("extra", None)
        if isinstance(extra, Mapping):
            context.update(extra)

        sanitized = log_context(**context)
        if sanitized:
            formatted = " ".join(f"{key}={value}" for key, value in sanitized.items())
            msg = f"{msg} | {formatted}"
            kwargs["extra"] = sanitized

        return msg, kwargs


def get_logger(name: str, **context: Any) -> ContextLoggerAdapter:
    """Return a logger adapter seeded with optional context."""
    return ContextLoggerAdapter(logging.getLogger(name), log_context(**context))


def bind_logger(
    logger_obj: logging.Logger | ContextLoggerAdapter, **context: Any
) -> ContextLoggerAdapter:
    """Bind additional context to an existing logger."""
    if isinstance(logger_obj, ContextLoggerAdapter):
        merged = dict(logger_obj.extra or {})
        merged.update(context)
        return ContextLoggerAdapter(logger_obj.logger, log_context(**merged))
    return ContextLoggerAdapter(logger_obj, log_context(**context))


def new_request_id() -> str:
    """Generate a short request identifier."""
    return uuid.uuid4().hex[:12]


__all__ = [
    "ContextLoggerAdapter",
    "bind_logger",
    "get_logger",
    "log_context",
    "new_request_id",
    "sanitize_label",
    "setup_logging",
]
