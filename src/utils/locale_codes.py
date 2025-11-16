"""Locale constants and helpers used across the application."""

from __future__ import annotations


SUPPORTED_LOCALES: tuple[str, ...] = ("en", "ru", "de")


def normalize_locale_code(locale_code: str | None) -> str | None:
    """Normalize locale codes such as 'en-US' to supported short codes."""
    if not locale_code:
        return None
    code = locale_code.split("-", 1)[0].split("_", 1)[0].strip().lower()
    if not code:
        return None
    if code in SUPPORTED_LOCALES:
        return code
    return None
