from __future__ import annotations

from dataclasses import dataclass
from importlib import resources
from typing import Any, cast

import yaml
from telegramify_markdown import markdownify

from .locale_codes import SUPPORTED_LOCALES, normalize_locale_code
from .logging import get_logger, log_context


class _SafeFormatDict(dict):
    """Dict that leaves unknown placeholders untouched."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass(slots=True, frozen=True)
class MissingNotice:
    request_id: str | None
    locale: str
    key: str


class I18n:
    """Simple YAML-backed localization helper with caching and logging."""

    _FALLBACK_LOCALE = "en"

    def __init__(self) -> None:
        self._catalog_cache: dict[str, dict[str, str]] = {}
        self._missing_notices: set[MissingNotice] = set()
        self._logger = get_logger(__name__)

    def reset(self) -> None:
        """Reset loaded catalogs and warning tracking (used in tests)."""
        self._catalog_cache.clear()
        self._missing_notices.clear()

    @staticmethod
    def normalize(locale: str | None) -> str:
        """Normalize locale codes and fall back to the default."""
        return normalize_locale_code(locale) or I18n._FALLBACK_LOCALE

    def translate(
        self,
        key: str,
        *,
        locale: str | None = None,
        request_id: str | None = None,
        should_markdownify: bool = True,
        **params: Any,
    ) -> str:
        """Translate a key for the desired locale with formatting parameters."""
        normalized = self.normalize(locale)
        template = self._get_template(normalized, key)
        if template is None and normalized != self._FALLBACK_LOCALE:
            self._warn_missing(normalized, key, request_id)
            template = self._get_template(self._FALLBACK_LOCALE, key)
        if template is None:
            self._warn_missing(self._FALLBACK_LOCALE, key, request_id)
            return key

        try:
            formatted_text = template.format_map(_SafeFormatDict(params))
            if should_markdownify:
                return cast(str, markdownify(formatted_text))
            return formatted_text
        except Exception as exc:  # pragma: no cover - defensive formatting guard
            self._logger.error(
                "Failed to render translation template",
                extra=log_context(
                    operation="i18n.translate",
                    locale=normalized,
                    meta_key=key,
                    meta_error=str(exc),
                ),
            )
            return template

    def _get_template(self, locale: str, key: str) -> str | None:
        catalog = self._catalog_cache.get(locale)
        if catalog is None:
            catalog = self._load_catalog(locale)
        return catalog.get(key)

    def _load_catalog(self, locale: str) -> dict[str, str]:
        """Load and cache the translation catalog for the locale."""
        if locale in self._catalog_cache:
            return self._catalog_cache[locale]

        try:
            package = "src.locales"
            resource = resources.files(package).joinpath(f"{locale}.yaml")
            with resource.open("r", encoding="utf-8") as handle:
                raw_catalog = yaml.safe_load(handle) or {}
        except FileNotFoundError:
            self._logger.warning(
                "Missing locale catalog; falling back to English",
                extra=log_context(operation="i18n.load_catalog", locale=locale),
            )
            raw_catalog = {}

        flattened = self._flatten_catalog(raw_catalog)
        self._catalog_cache[locale] = flattened
        return flattened

    def _flatten_catalog(
        self,
        data: dict[str, Any],
        *,
        parent_key: str = "",
    ) -> dict[str, str]:
        """Flatten nested YAML dictionaries into dotted keys."""
        items: dict[str, str] = {}
        for key, value in data.items():
            full_key = f"{parent_key}.{key}" if parent_key else str(key)
            if isinstance(value, dict):
                items.update(self._flatten_catalog(value, parent_key=full_key))
            else:
                items[full_key] = str(value)
        return items

    def _warn_missing(self, locale: str, key: str, request_id: str | None) -> None:
        notice = MissingNotice(request_id=request_id, locale=locale, key=key)
        if notice in self._missing_notices:
            return
        self._missing_notices.add(notice)
        self._logger.warning(
            "Missing translation key; using fallback",
            extra=log_context(
                operation="i18n.missing_key",
                request_id=request_id,
                locale=locale,
                meta_key=key,
            ),
        )


i18n = I18n()
translate = i18n.translate
normalize_locale = I18n.normalize
__all__ = ["i18n", "translate", "normalize_locale", "normalize_locale_code", "SUPPORTED_LOCALES"]
