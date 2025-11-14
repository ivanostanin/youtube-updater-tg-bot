import logging
import logging.handlers
import sys
from pathlib import Path
from threading import Lock

from .config import settings


class UnbufferedStreamHandler(logging.StreamHandler):
    """Stream handler that forces immediate flushing."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        self.flush()


_logging_lock = Lock()
_logging_configured = False


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

        # Create formatters
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )

        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(log_level)

        # Clear any existing handlers to avoid duplicates
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)

        # Create console handler with immediate flushing
        console_handler = UnbufferedStreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        console_handler.setLevel(log_level)

        # Create file handler
        file_handler = logging.FileHandler(logs_dir / "bot.log", mode="a")
        file_handler.setFormatter(formatter)
        file_handler.setLevel(log_level)

        # Add our handlers
        root_logger.addHandler(console_handler)
        root_logger.addHandler(file_handler)

        # Set specific loggers
        logging.getLogger("telegram").setLevel(logging.INFO)
        logging.getLogger("httpx").setLevel(logging.WARNING)
        logging.getLogger("uvicorn").setLevel(logging.INFO)

        # Configure asyncio logger to be more verbose in debug mode
        if log_level <= logging.DEBUG:
            logging.getLogger("asyncio").setLevel(logging.DEBUG)

        # Test log message
        logger = logging.getLogger(__name__)
        logger.info("Logging system initialized successfully")

        _logging_configured = True
        return logger
