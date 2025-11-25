"""Storage configuration utilities for backup and restore scripts."""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass
from typing import Any, Final

from .exceptions import StorageConfigurationError


_ENV_PREFIX: Final[str] = "OBJECT_STORAGE_"
_DEFAULT_PREFIX: Final[str] = "db-backups/"
_DEFAULT_REGION: Final[str] = "us-east-1"


def _parse_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "y", "on"}


def _normalize_prefix(prefix: str | None) -> str:
    if not prefix:
        return ""
    if not prefix.endswith("/"):
        return f"{prefix}/"
    return prefix


@dataclass(slots=True)
class ObjectStorageConfig:
    """Resolved configuration for accessing S3-compatible storage."""

    endpoint_url: str | None
    namespace: str | None
    region: str
    bucket: str
    prefix: str
    access_key: str | None
    secret_key: str | None
    use_namespace_path: bool
    verify_ssl: bool
    profile_name: str | None = None

    def is_configured(self) -> bool:
        """Return True when configuration contains sufficient data."""
        return bool(self.bucket)

    @property
    def bucket_name(self) -> str:
        """Return bucket name including namespace path if configured."""
        if self.use_namespace_path and self.namespace:
            if self.bucket.startswith(f"{self.namespace}/"):
                return self.bucket
            return f"{self.namespace}/{self.bucket}"
        return self.bucket

    def create_client(self) -> Any:
        """Create a boto3 S3 client for the configuration."""
        try:
            import boto3
        except ModuleNotFoundError as exc:  # pragma: no cover - defensive
            raise StorageConfigurationError("boto3 is required for storage operations") from exc

        session = boto3.session.Session(
            region_name=self.region,
            profile_name=self.profile_name,
        )

        client_kwargs: dict[str, Any] = {}
        if self.endpoint_url:
            client_kwargs["endpoint_url"] = self.endpoint_url
        if self.access_key:
            client_kwargs["aws_access_key_id"] = self.access_key
        if self.secret_key:
            client_kwargs["aws_secret_access_key"] = self.secret_key
        client_kwargs["verify"] = self.verify_ssl
        return session.client("s3", **client_kwargs)


def add_storage_arguments(parser: argparse.ArgumentParser) -> None:
    """Add shared storage configuration arguments to an ArgumentParser."""
    parser.add_argument("--endpoint-url", dest="endpoint_url", help="S3-compatible endpoint URL")
    parser.add_argument("--namespace", dest="namespace", help="OCI object storage namespace")
    parser.add_argument("--region", dest="region", help="Object storage region")
    parser.add_argument("--bucket", dest="bucket", help="Bucket name for backups")
    parser.add_argument(
        "--prefix",
        dest="prefix",
        help="Object key prefix (defaults to db-backups/)",
    )
    parser.add_argument(
        "--access-key",
        dest="access_key",
        help="Access key ID for the storage provider",
    )
    parser.add_argument(
        "--secret-key",
        dest="secret_key",
        help="Secret key for the storage provider",
    )
    parser.add_argument(
        "--use-namespace-path",
        dest="use_namespace_path",
        action="store_true",
        help="Prefix bucket path with namespace (namespace/bucket) for OCI compatibility",
    )
    parser.add_argument(
        "--no-namespace-path",
        dest="use_namespace_path",
        action="store_false",
        help="Do not prefix bucket path with namespace (default for AWS S3)",
    )
    parser.add_argument(
        "--no-verify-ssl",
        dest="verify_ssl",
        action="store_false",
        help="Disable TLS certificate verification (not recommended)",
    )
    parser.add_argument(
        "--profile",
        dest="profile_name",
        help="Optional AWS/OCI CLI profile name",
    )
    parser.set_defaults(use_namespace_path=None, verify_ssl=None)


def build_storage_config(
    args: argparse.Namespace | None = None,
    *,
    require_bucket: bool = True,
) -> ObjectStorageConfig:
    """Build storage configuration from environment variables and CLI args.

    Parameters
    ----------
    args:
        Parsed CLI namespace providing overrides for storage fields.
    require_bucket:
        When ``True`` (default), raise ``StorageConfigurationError`` if no bucket
        configuration is present. When ``False``, return a partially configured
        ``ObjectStorageConfig`` so callers can decide how to proceed.
    """

    def _env(name: str, default: str | None = None) -> str | None:
        return os.getenv(f"{_ENV_PREFIX}{name}", default)

    endpoint = _env("ENDPOINT") or os.getenv("S3_ENDPOINT")
    namespace = _env("NAMESPACE")
    region = (
        (args.region if args and getattr(args, "region", None) else None)
        or _env("REGION")
        or os.getenv("AWS_REGION")
        or _DEFAULT_REGION
    )
    bucket = (
        (args.bucket if args and getattr(args, "bucket", None) else None)
        or _env("BUCKET")
        or os.getenv("S3_BUCKET")
        or ""
    ).strip()
    prefix = (
        (args.prefix if args and getattr(args, "prefix", None) else None)
        or _env("PREFIX")
        or _DEFAULT_PREFIX
    )
    access_key = (
        (args.access_key if args and getattr(args, "access_key", None) else None)
        or _env("ACCESS_KEY")
        or os.getenv("AWS_ACCESS_KEY_ID")
    )
    secret_key = (
        (args.secret_key if args and getattr(args, "secret_key", None) else None)
        or _env("SECRET_KEY")
        or os.getenv("AWS_SECRET_ACCESS_KEY")
    )

    if args and getattr(args, "endpoint_url", None):
        endpoint = args.endpoint_url
    if args and getattr(args, "namespace", None):
        namespace = args.namespace

    if args and getattr(args, "profile_name", None):
        profile = args.profile_name
    else:
        profile = os.getenv("AWS_PROFILE") or os.getenv("OCI_PROFILE")

    raw_use_namespace_path = (
        getattr(args, "use_namespace_path", None)
        if args and args.use_namespace_path is not None
        else _parse_bool(_env("USE_NAMESPACE_PATH"), default=False)
    )
    raw_verify_ssl = (
        getattr(args, "verify_ssl", None)
        if args and args.verify_ssl is not None
        else _parse_bool(_env("VERIFY_SSL"), default=True)
    )
    use_namespace_path = (
        bool(raw_use_namespace_path) if raw_use_namespace_path is not None else False
    )
    verify_ssl = bool(raw_verify_ssl) if raw_verify_ssl is not None else True

    config = ObjectStorageConfig(
        endpoint_url=endpoint,
        namespace=namespace,
        region=region,
        bucket=bucket,
        prefix=_normalize_prefix(prefix),
        access_key=access_key,
        secret_key=secret_key,
        use_namespace_path=use_namespace_path,
        verify_ssl=verify_ssl,
        profile_name=profile,
    )

    if require_bucket and not config.bucket:
        raise StorageConfigurationError(
            "OBJECT_STORAGE_BUCKET (or --bucket) must be set for backup operations.",
        )

    return config
