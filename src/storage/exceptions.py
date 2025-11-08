"""Custom exceptions for storage operations."""


class StorageConfigurationError(ValueError):
    """Raised when storage configuration is invalid or incomplete."""


class RestoreError(RuntimeError):
    """Base class for restore-related errors."""


class BackupNotFoundError(RestoreError):
    """Raised when no backups are available to restore."""


class ChecksumMismatchError(RestoreError):
    """Raised when a restored file does not match the recorded checksum."""
