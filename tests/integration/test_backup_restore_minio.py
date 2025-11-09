"""Integration tests against a MinIO S3-compatible endpoint."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import allure
import boto3
import pytest

from src.storage.backup import perform_backup
from src.storage.config import ObjectStorageConfig
from src.storage.restore import restore_latest_backup


try:  # pragma: no cover - optional dependency
    import pytest_docker.plugin  # noqa: F401

    HAVE_PYTEST_DOCKER = True
except ModuleNotFoundError:  # pragma: no cover - fallback for restricted envs
    HAVE_PYTEST_DOCKER = False


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not HAVE_PYTEST_DOCKER,
        reason="pytest-docker is required for MinIO integration tests.",
    ),
]


FEATURE = "Backup-Restore"
STORY = "Oracle Cloud Backup Restore"
MINIO_ACCESS_KEY = "minioadmin"
MINIO_SECRET_KEY = "minioadmin"
MINIO_REGION = "us-east-1"
MINIO_BUCKET = "ci-backup-tests"


def _require_docker() -> None:
    if not shutil.which("docker"):
        pytest.skip("Docker is required for MinIO integration tests.")
    try:
        subprocess.run(
            ["docker", "info"],
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        pytest.skip(f"Docker daemon unavailable: {exc}")


@pytest.fixture(scope="session")
def docker_compose_file(pytestconfig: pytest.Config) -> Path:
    """Provide docker-compose definition for pytest-docker."""
    _require_docker()
    return Path(__file__).with_name("docker-compose-minio.yaml")


@pytest.fixture(scope="session")
def minio_endpoint(docker_services, docker_ip) -> str:
    """Start MinIO via docker-compose and return the endpoint URL."""
    _require_docker()
    port = docker_services.port_for("minio", 9000)
    endpoint = f"http://{docker_ip}:{port}"

    def _is_responsive() -> bool:
        client = boto3.client(
            "s3",
            endpoint_url=endpoint,
            aws_access_key_id=MINIO_ACCESS_KEY,
            aws_secret_access_key=MINIO_SECRET_KEY,
            region_name=MINIO_REGION,
            verify=False,
        )
        try:
            client.list_buckets()
        except Exception:  # pragma: no cover - wait until ready
            return False
        return True

    docker_services.wait_until_responsive(check=_is_responsive, timeout=60.0, pause=1.5)
    return endpoint


@pytest.fixture()
def minio_client(minio_endpoint: str):
    """Return a boto3 client pointing at the MinIO instance."""
    return boto3.client(
        "s3",
        endpoint_url=minio_endpoint,
        aws_access_key_id=MINIO_ACCESS_KEY,
        aws_secret_access_key=MINIO_SECRET_KEY,
        region_name=MINIO_REGION,
        verify=False,
    )


def _ensure_bucket(client: Any, bucket: str) -> None:
    existing = client.list_buckets().get("Buckets", [])
    names = {entry["Name"] for entry in existing}
    if bucket not in names:
        client.create_bucket(Bucket=bucket)


def _make_config(endpoint: str) -> ObjectStorageConfig:
    return ObjectStorageConfig(
        endpoint_url=endpoint,
        namespace=None,
        region=MINIO_REGION,
        bucket=MINIO_BUCKET,
        prefix="db-backups/",
        access_key=MINIO_ACCESS_KEY,
        secret_key=MINIO_SECRET_KEY,
        use_namespace_path=False,
        verify_ssl=False,
        profile_name=None,
    )


@allure.feature(FEATURE)
@allure.story(STORY)
@allure.label("test_id", "1.2-INT-006")
@allure.label("level", "Integration")
@allure.label("priority", "P0")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.integration
@pytest.mark.slow
def test_backup_and_restore_pipeline_against_minio(
    minio_endpoint: str,
    minio_client,
    tmp_path: Path,
):
    """Backup and restore end-to-end using MinIO."""
    _ensure_bucket(minio_client, MINIO_BUCKET)
    config = _make_config(minio_endpoint)

    database = tmp_path / "bot.db"
    database.write_text("integration-backup")

    backup_result = perform_backup(config, database, client=minio_client)
    objects = minio_client.list_objects_v2(Bucket=MINIO_BUCKET)
    keys = [item["Key"] for item in objects.get("Contents", [])]
    assert backup_result["key"] in keys

    # Simulate restore flow
    database.unlink()
    restored_path = tmp_path / "restored.db"
    restore_latest_backup(config, restored_path, client=minio_client)
    assert restored_path.read_text() == "integration-backup"


@allure.feature(FEATURE)
@allure.story(STORY)
@allure.label("test_id", "1.2-INT-005")
@allure.label("level", "Integration")
@allure.label("priority", "P1")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
@pytest.mark.slow
def test_lifecycle_policy_command_supported(minio_endpoint: str, minio_client):
    """Ensure lifecycle policy enforcement commands succeed against MinIO."""
    _ensure_bucket(minio_client, MINIO_BUCKET)
    rules = {
        "Rules": [
            {
                "ID": "expire-backups",
                "Status": "Enabled",
                "Filter": {"Prefix": "db-backups/"},
                "Expiration": {"Days": 30},
            }
        ]
    }
    minio_client.put_bucket_lifecycle_configuration(
        Bucket=MINIO_BUCKET,
        LifecycleConfiguration=rules,
    )

    response = minio_client.get_bucket_lifecycle_configuration(Bucket=MINIO_BUCKET)
    assert response["Rules"][0]["Expiration"]["Days"] == 30
