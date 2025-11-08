#!/usr/bin/env python3
"""Upload the SQLite database to S3-compatible object storage."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.storage_config import (  # noqa: E402
    StorageConfigurationError,
    add_storage_arguments,
    build_storage_config,
)

from src.storage.backup import perform_backup  # noqa: E402


logger = logging.getLogger("backup-db")


def _default_database_path() -> str:
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
        description="Back up the SQLite database to an S3-compatible bucket.",
    )
    add_storage_arguments(parser)
    parser.add_argument(
        "--database-path",
        default=_default_database_path(),
        help="Path to the SQLite database file (default: %(default)s)",
    )
    parser.add_argument(
        "--object-prefix",
        dest="object_prefix",
        help="Override object key prefix (defaults to configured prefix)",
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

    database_path = args.database_path
    try:
        result: dict[str, Any] = perform_backup(
            config,
            database_path,
            object_prefix=args.object_prefix,
        )
    except FileNotFoundError as exc:
        logger.error("Database file not found at %s", database_path)
        raise SystemExit(3) from exc
    except Exception as exc:  # pragma: no cover - defensive logging
        logger.exception("Unexpected error during backup")
        raise SystemExit(1) from exc

    logger.info(
        "Backup completed successfully",
        extra={
            "bucket": result["bucket"],
            "key": result["key"],
            "checksum": result["checksum"],
            "size_bytes": result["size"],
        },
    )


if __name__ == "__main__":
    main()
