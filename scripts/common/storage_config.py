"""Compatibility layer exposing storage configuration helpers to scripts."""

from __future__ import annotations

import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.storage.config import (  # noqa: E402
    ObjectStorageConfig,
    add_storage_arguments,
    build_storage_config,
)
from src.storage.exceptions import StorageConfigurationError  # noqa: E402


__all__ = [
    "ObjectStorageConfig",
    "StorageConfigurationError",
    "add_storage_arguments",
    "build_storage_config",
]
