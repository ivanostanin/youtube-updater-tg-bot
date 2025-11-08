"""Startup utilities for automatic database restoration."""

from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

from .config import build_storage_config
from .exceptions import BackupNotFoundError, RestoreError, StorageConfigurationError
from .restore import restore_latest_backup


logger = logging.getLogger(__name__)


def _resolve_database_path(database_url: str) -> Path | None:
    try:
        url = make_url(database_url)
    except ArgumentError:
        logger.warning(
            "Unable to parse database URL; skipping auto-restore", extra={"url": database_url}
        )
        return None

    if not url.drivername.startswith("sqlite"):
        logger.debug(
            "Auto-restore only applies to SQLite URLs; skipping", extra={"driver": url.drivername}
        )
        return None

    if not url.database:
        logger.warning(
            "SQLite URL does not include a database path; skipping restore",
            extra={"url": database_url},
        )
        return None

    path = Path(url.database)
    return path.expanduser().resolve()


def ensure_database_backup(database_url: str, *, force: bool = False) -> None:
    """Ensure the SQLite database exists, restoring the latest backup if necessary."""
    db_path = _resolve_database_path(database_url)
    if db_path is None:
        return

    if db_path.exists() and not force:
        logger.info("Database already present; skipping auto-restore", extra={"path": str(db_path)})
        return

    try:
        config = build_storage_config()
    except StorageConfigurationError as exc:
        logger.warning(
            "Object storage configuration incomplete; skipping database auto-restore",
            extra={"reason": str(exc)},
        )
        return

    try:
        restore_latest_backup(config, db_path)
    except BackupNotFoundError:
        logger.warning(
            "No backups available; continuing without restored database",
            extra={"bucket": config.bucket_name, "prefix": config.prefix},
        )
    except RestoreError as exc:
        logger.error(
            "Database restore failed; aborting startup",
            extra={"error": str(exc), "bucket": config.bucket_name},
        )
        raise
