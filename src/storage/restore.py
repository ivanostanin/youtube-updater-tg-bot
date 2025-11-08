"""Restore helpers for database backups."""

from __future__ import annotations

import hashlib
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import ObjectStorageConfig
from .exceptions import (
    BackupNotFoundError,
    ChecksumMismatchError,
    StorageConfigurationError,
)


logger = logging.getLogger(__name__)


def _object_timestamp(key: str) -> datetime | None:
    try:
        base = key.rsplit("/", maxsplit=1)[-1]
        timestamp_part = base.removeprefix("bot-").removesuffix(".db")
        return datetime.strptime(timestamp_part, "%Y-%m-%dT%H-%M-%SZ")
    except ValueError:
        return None


def _list_backups(client: Any, bucket: str, prefix: str) -> list[dict[str, Any]]:
    kwargs: dict[str, Any] = {"Bucket": bucket}
    if prefix:
        kwargs["Prefix"] = prefix

    response = client.list_objects_v2(**kwargs)
    objects = response.get("Contents", [])
    while response.get("IsTruncated"):
        kwargs["ContinuationToken"] = response.get("NextContinuationToken")
        response = client.list_objects_v2(**kwargs)
        objects.extend(response.get("Contents", []))
    return objects


def _select_latest(objects: list[dict[str, Any]]) -> dict[str, Any]:
    if not objects:
        raise BackupNotFoundError("No backups available in object storage bucket.")

    def _sort_key(obj: dict[str, Any]) -> tuple[datetime, str]:
        last_modified = obj.get("LastModified")
        if isinstance(last_modified, datetime):
            sort_dt = (
                last_modified.replace(tzinfo=UTC)
                if last_modified.tzinfo is None
                else last_modified.astimezone(UTC)
            )
            return sort_dt, obj["Key"]
        parsed = _object_timestamp(obj["Key"])
        if parsed:
            return parsed.replace(tzinfo=UTC), obj["Key"]
        return datetime.min.replace(tzinfo=UTC), obj["Key"]

    return max(objects, key=_sort_key)


def restore_latest_backup(
    config: ObjectStorageConfig,
    destination_path: str | Path,
    *,
    client: Any | None = None,
) -> Path:
    """Restore the most recent backup to the destination path."""
    if not config.is_configured():
        raise StorageConfigurationError("Storage configuration is incomplete; bucket is required.")

    dest_path = Path(destination_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)

    storage_client = client or config.create_client()
    backups = _list_backups(storage_client, config.bucket_name, config.prefix)
    latest = _select_latest(backups)
    object_key = latest["Key"]

    logger.info(
        "Restoring database from object storage",
        extra={"bucket": config.bucket_name, "key": object_key},
    )

    response = storage_client.get_object(Bucket=config.bucket_name, Key=object_key)
    metadata = {k.lower(): v for k, v in response.get("Metadata", {}).items()}
    body = response["Body"].read()

    expected_checksum = metadata.get("sha256")
    expected_size = metadata.get("size")
    timestamp = metadata.get("timestamp")

    if expected_checksum is None:
        raise ChecksumMismatchError(
            f"Backup object {object_key} is missing checksum metadata (sha256).",
        )

    computed_checksum = hashlib.sha256(body).hexdigest()
    if computed_checksum != expected_checksum:
        raise ChecksumMismatchError(
            f"Checksum mismatch for {object_key}: expected {expected_checksum}, got {computed_checksum}",
        )

    if expected_size is not None and str(len(body)) != expected_size:
        raise ChecksumMismatchError(
            f"Size mismatch for {object_key}: expected {expected_size} bytes, got {len(body)}",
        )

    dest_path.write_bytes(body)
    logger.info(
        "Database restore completed",
        extra={
            "destination": str(dest_path),
            "bucket": config.bucket_name,
            "key": object_key,
            "timestamp": timestamp,
        },
    )

    return dest_path
