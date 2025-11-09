"""Integration tests validating Helm CronJob rendering for database backups."""

from __future__ import annotations

import shutil
import subprocess
from collections.abc import Iterable, Mapping
from pathlib import Path

import allure
import pytest
import yaml


CHART_DIR = Path(__file__).resolve().parents[2] / "deployment" / "helm" / "youtube-updater-tg-bot"


def _require_helm() -> None:
    if not shutil.which("helm"):
        pytest.skip("helm binary is required for Helm template rendering tests")


FEATURE = "Backup-Restore"
STORY = "Oracle Cloud Backup Restore"


def _render_chart(extra_set: Mapping[str, str] | None = None) -> list[dict]:
    """Render the Helm chart with optional overrides and return parsed manifests."""
    _require_helm()
    command: list[str] = ["helm", "template", "test-release", str(CHART_DIR)]
    for key, value in (extra_set or {}).items():
        command.extend(["--set", f"{key}={value}"])

    result = subprocess.run(
        command,
        check=True,
        capture_output=True,
        text=True,
    )
    documents = [doc for doc in yaml.safe_load_all(result.stdout) if doc]
    return documents


def _find_kind(documents: Iterable[dict], kind: str) -> list[dict]:
    return [doc for doc in documents if doc.get("kind") == kind]


@allure.feature(FEATURE)
@allure.story(STORY)
@allure.label("test_id", "1.2-INT-003A")
@allure.label("level", "Integration")
@allure.label("priority", "P1")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.integration
def test_backup_cronjob_not_rendered_without_object_storage():
    """CronJob is omitted when object storage is disabled."""
    documents = _render_chart(
        {
            "objectStorage.enabled": "false",
            "backupJob.enabled": "true",
            "persistence.enabled": "true",
        }
    )
    cronjobs = _find_kind(documents, "CronJob")
    assert not cronjobs, "CronJob should not render when object storage is disabled"


@allure.feature(FEATURE)
@allure.story(STORY)
@allure.label("test_id", "1.2-INT-003")
@allure.label("level", "Integration")
@allure.label("priority", "P1")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
def test_backup_cronjob_renders_with_expected_environment():
    """CronJob renders when object storage enabled with complete env wiring."""
    overrides = {
        "objectStorage.enabled": "true",
        "objectStorage.endpoint": "https://compat.objectstorage.test",
        "objectStorage.namespace": "demo",
        "objectStorage.region": "us-ashburn-1",
        "objectStorage.bucket": "backups",
        "objectStorage.accessKey": "demo-access",
        "objectStorage.secretKey": "demo-secret",
        "backupJob.schedule": "5 3 * * *",
    }
    documents = _render_chart(overrides)
    cronjobs = _find_kind(documents, "CronJob")
    assert cronjobs, "CronJob manifest should render when object storage is enabled"

    cronjob = cronjobs[0]
    assert cronjob["spec"]["schedule"] == "5 3 * * *"
    container = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]

    env_names = {entry["name"] for entry in container["env"]}
    expected_env = {
        "OBJECT_STORAGE_ENDPOINT",
        "OBJECT_STORAGE_NAMESPACE",
        "OBJECT_STORAGE_REGION",
        "OBJECT_STORAGE_BUCKET",
        "OBJECT_STORAGE_PREFIX",
        "OBJECT_STORAGE_USE_NAMESPACE_PATH",
        "OBJECT_STORAGE_VERIFY_SSL",
        "OBJECT_STORAGE_LIFECYCLE_DAYS",
        "OBJECT_STORAGE_ACCESS_KEY",
        "OBJECT_STORAGE_SECRET_KEY",
    }
    missing = expected_env.difference(env_names)
    assert not missing, f"Missing expected environment variables: {sorted(missing)}"

    access_key_env = next(
        entry for entry in container["env"] if entry["name"] == "OBJECT_STORAGE_ACCESS_KEY"
    )
    secret_key_env = next(
        entry for entry in container["env"] if entry["name"] == "OBJECT_STORAGE_SECRET_KEY"
    )
    config_env = next(
        entry for entry in container["env"] if entry["name"] == "OBJECT_STORAGE_ENDPOINT"
    )

    assert access_key_env["valueFrom"]["secretKeyRef"]["key"] == "object-storage-access-key"
    assert secret_key_env["valueFrom"]["secretKeyRef"]["key"] == "object-storage-secret-key"
    assert config_env["valueFrom"]["configMapKeyRef"]["key"] == "object-storage-endpoint"

    volumes = cronjob["spec"]["jobTemplate"]["spec"]["template"]["spec"]["volumes"]
    assert volumes, "Expected data volume to be mounted"
    pvc = volumes[0]["persistentVolumeClaim"]
    assert pvc["claimName"].startswith("data-test-release"), "CronJob should mount StatefulSet PVC"
