#!/usr/bin/env python3
"""Restore the latest SQLite database backup from object storage."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.storage_config import (  # noqa: E402
    StorageConfigurationError,
    add_storage_arguments,
    build_storage_config,
)

from src.storage.exceptions import (  # noqa: E402
    BackupNotFoundError,
    ChecksumMismatchError,
    RestoreError,
)
from src.storage.restore import restore_latest_backup  # noqa: E402


logger = logging.getLogger("restore-db")


def _default_destination_path() -> str:
    return os.getenv("DATABASE_PATH", "/app/data/bot.db")


def _configure_logging() -> None:
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Restore the latest backup from an S3-compatible bucket.",
    )
    add_storage_arguments(parser)
    parser.add_argument(
        "--destination-path",
        default=_default_destination_path(),
        help="Path to write the restored database file (default: %(default)s)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination if it already exists",
    )
    return parser.parse_args()


def main() -> None:
    _configure_logging()
    args = parse_args()
    try:
        config = build_storage_config(args)
    except StorageConfigurationError as exc:
        logger.error("Storage configuration error: %s", exc)
        raise SystemExit(2) from exc

    destination = Path(args.destination_path)
    if destination.exists() and not args.force:
        logger.info("Destination file already exists; skipping restore (use --force to override)")
        return

    try:
        restored_path = restore_latest_backup(config, destination)
    except BackupNotFoundError as exc:
        logger.warning("No backups available to restore: %s", exc)
        raise SystemExit(4) from exc
    except ChecksumMismatchError as exc:
        logger.error("Checksum validation failed: %s", exc)
        raise SystemExit(5) from exc
    except RestoreError as exc:
        logger.error("Restore failed: %s", exc)
        raise SystemExit(6) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected error during restore")
        raise SystemExit(1) from exc

    logger.info("Database restored to %s", restored_path)


if __name__ == "__main__":
    main()
