"""Database backup helpers."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ObjectStorageConfig
from .exceptions import StorageConfigurationError


logger = logging.getLogger(__name__)


def _compute_checksum(payload: bytes) -> tuple[str, int]:
    digest = hashlib.sha256(payload).hexdigest()
    return digest, len(payload)


def perform_backup(
    config: ObjectStorageConfig,
    database_path: str | Path,
    *,
    client: Any | None = None,
    object_prefix: str | None = None,
) -> dict[str, Any]:
    """Upload the SQLite database to object storage.

    Args:
        config: Storage configuration.
        database_path: Path to the SQLite database file.
        client: Optional boto3 client (useful for tests).
        object_prefix: Optional override for the key prefix.

    Returns:
        Details about the uploaded backup object.
    """
    if not config.is_configured():
        raise StorageConfigurationError("Storage configuration is incomplete; bucket is required.")

    resolved_prefix = object_prefix if object_prefix is not None else config.prefix
    if resolved_prefix and not resolved_prefix.endswith("/"):
        resolved_prefix = f"{resolved_prefix}/"

    db_path = Path(database_path)
    if not db_path.exists():
        raise FileNotFoundError(f"Database file not found at {db_path}")

    payload = db_path.read_bytes()
    checksum, size = _compute_checksum(payload)
    timestamp = datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")
    object_key = (
        f"{resolved_prefix}bot-{timestamp}.db" if resolved_prefix else f"bot-{timestamp}.db"
    )

    storage_client = client or config.create_client()
    metadata = {
        "timestamp": timestamp,
        "sha256": checksum,
        "size": str(size),
    }
    if config.namespace:
        metadata["namespace"] = config.namespace

    logger.info(
        "Uploading database backup",
        extra={
            "bucket": config.bucket_name,
            "key": object_key,
            "size_bytes": size,
            "endpoint": config.endpoint_url or "aws-s3-default",
        },
    )

    storage_client.put_object(
        Bucket=config.bucket_name,
        Key=object_key,
        Body=payload,
        Metadata=metadata,
    )

    logger.info(
        "Database backup upload complete",
        extra={"bucket": config.bucket_name, "key": object_key, "checksum": checksum},
    )

    return {
        "bucket": config.bucket_name,
        "key": object_key,
        "checksum": checksum,
        "size": size,
        "timestamp": timestamp,
    }
