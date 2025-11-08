"""Unit tests for backup and restore utilities."""

from __future__ import annotations

import hashlib
import io
from datetime import UTC, datetime

import pytest

from src.storage import startup
from src.storage.backup import perform_backup
from src.storage.config import ObjectStorageConfig, build_storage_config
from src.storage.exceptions import (
    BackupNotFoundError,
    ChecksumMismatchError,
    StorageConfigurationError,
)
from src.storage.restore import restore_latest_backup


class FakeBackupClient:
    """In-memory stub for boto3 S3 client methods used in backup/restore."""

    def __init__(
        self,
        *,
        objects: list[dict] | None = None,
        body: bytes | None = None,
        metadata: dict | None = None,
    ):
        self.objects = objects or []
        self.body = body or b""
        self.metadata = metadata or {}
        self.put_calls: list[dict] = []
        self.list_calls: list[dict] = []
        self.get_calls: list[dict] = []

    # Backup helpers -----------------------------------------------------
    def put_object(self, **kwargs):
        self.put_calls.append(kwargs)

    # Restore helpers ----------------------------------------------------
    def list_objects_v2(self, **kwargs):
        self.list_calls.append(kwargs)
        if not self.objects:
            return {"KeyCount": 0}
        return {"KeyCount": len(self.objects), "Contents": self.objects, "IsTruncated": False}

    def get_object(self, **kwargs):
        self.get_calls.append(kwargs)
        return {"Body": io.BytesIO(self.body), "Metadata": self.metadata}


def _make_config(bucket: str = "test-bucket", **overrides) -> ObjectStorageConfig:
    base = {
        "endpoint_url": "https://objectstorage.example.com",
        "namespace": "mynamespace",
        "region": "us-test-1",
        "bucket": bucket,
        "prefix": "db-backups/",
        "access_key": "access",
        "secret_key": "secret",
        "use_namespace_path": overrides.get("use_namespace_path", False),
        "verify_ssl": True,
        "profile_name": None,
    }
    base.update(overrides)
    return ObjectStorageConfig(**base)


def test_build_storage_config_from_environment(monkeypatch):
    """Ensure environment variables populate configuration fields."""
    monkeypatch.setenv("OBJECT_STORAGE_BUCKET", "demo-bucket")
    monkeypatch.setenv("OBJECT_STORAGE_REGION", "eu-frankfurt-1")
    monkeypatch.setenv("OBJECT_STORAGE_PREFIX", "sqlite/")
    monkeypatch.setenv("OBJECT_STORAGE_USE_NAMESPACE_PATH", "true")

    config = build_storage_config(None)

    assert config.bucket == "demo-bucket"
    assert config.region == "eu-frankfurt-1"
    assert config.prefix == "sqlite/"
    assert config.use_namespace_path is True


def test_perform_backup_uploads_with_metadata(tmp_path):
    """Verify uploads contain checksum metadata and use namespace-prefixed bucket paths."""
    db_path = tmp_path / "bot.db"
    db_path.write_text("database")

    config = _make_config(use_namespace_path=True)
    client = FakeBackupClient()

    result = perform_backup(config, db_path, client=client)

    assert client.put_calls, "Expected put_object to be called"
    call = client.put_calls[0]
    assert call["Bucket"] == "mynamespace/test-bucket"
    assert "Metadata" in call
    assert call["Metadata"]["sha256"] == result["checksum"]
    assert call["Metadata"]["size"] == str(result["size"])
    assert result["key"].startswith("db-backups/bot-")


def test_restore_latest_backup_success(tmp_path):
    """Restore downloads the latest backup and writes contents to disk."""
    config = _make_config()
    timestamp = datetime(2025, 1, 1, 1, 0, tzinfo=UTC)
    body = b"restored database"
    checksum = hashlib.sha256(body).hexdigest()
    client = FakeBackupClient(
        objects=[{"Key": "db-backups/bot-2025-01-01T01-00-00Z.db", "LastModified": timestamp}],
        body=body,
        metadata={"sha256": checksum, "size": str(len(body))},
    )

    destination = tmp_path / "bot.db"
    result_path = restore_latest_backup(config, destination, client=client)

    assert result_path == destination
    assert destination.read_bytes() == body


def test_restore_latest_backup_missing_checksum(tmp_path):
    """Missing checksum metadata should raise an error."""
    config = _make_config()
    client = FakeBackupClient(
        objects=[
            {"Key": "db-backups/bot-2025-01-01T01-00-00Z.db", "LastModified": datetime.now(UTC)}
        ],
        body=b"payload",
        metadata={},  # Missing sha256
    )

    with pytest.raises(ChecksumMismatchError):
        restore_latest_backup(config, tmp_path / "bot.db", client=client)


def test_restore_latest_backup_not_found(tmp_path):
    """No available backups should raise BackupNotFoundError."""
    config = _make_config()
    client = FakeBackupClient(objects=[])

    with pytest.raises(BackupNotFoundError):
        restore_latest_backup(config, tmp_path / "bot.db", client=client)


def test_ensure_database_backup_skips_when_present(monkeypatch, tmp_path):
    """Auto-restore should not run when database already exists."""
    db_path = tmp_path / "bot.db"
    db_path.write_text("existing")

    monkeypatch.setattr(startup, "_resolve_database_path", lambda _: db_path)
    build_called = False

    def fake_build():
        nonlocal build_called
        build_called = True
        return _make_config()

    monkeypatch.setattr(startup, "build_storage_config", fake_build)
    startup.ensure_database_backup("sqlite+aiosqlite:///ignored")

    assert build_called is False
    assert db_path.read_text() == "existing"


def test_ensure_database_backup_handles_missing_configuration(monkeypatch, tmp_path):
    """Missing configuration should log and continue without raising."""
    db_path = tmp_path / "bot.db"

    monkeypatch.setattr(startup, "_resolve_database_path", lambda _: db_path)

    def fake_build():
        raise StorageConfigurationError("missing bucket")

    monkeypatch.setattr(startup, "build_storage_config", fake_build)
    startup.ensure_database_backup("sqlite+aiosqlite:///ignored")

    assert not db_path.exists()


def test_ensure_database_backup_restores_latest_backup(monkeypatch, tmp_path):
    """When database missing, ensure restore is invoked and file created."""
    db_path = tmp_path / "bot.db"

    monkeypatch.setattr(startup, "_resolve_database_path", lambda _: db_path)
    monkeypatch.setattr(startup, "build_storage_config", lambda: _make_config())

    restored = {"called": 0}

    def fake_restore(config, destination):
        restored["called"] += 1
        destination.write_text("restored")
        return destination

    monkeypatch.setattr(startup, "restore_latest_backup", fake_restore)
    startup.ensure_database_backup("sqlite+aiosqlite:///ignored")

    assert restored["called"] == 1
    assert db_path.read_text() == "restored"


def test_ensure_database_backup_warns_on_missing_backups(monkeypatch, tmp_path):
    """BackupNotFoundError should be swallowed to allow fresh database."""
    db_path = tmp_path / "bot.db"

    monkeypatch.setattr(startup, "_resolve_database_path", lambda _: db_path)
    monkeypatch.setattr(startup, "build_storage_config", lambda: _make_config())

    def fake_restore(config, destination):
        raise BackupNotFoundError("no backups")

    monkeypatch.setattr(startup, "restore_latest_backup", fake_restore)
    startup.ensure_database_backup("sqlite+aiosqlite:///ignored")

    assert not db_path.exists()
