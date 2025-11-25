"""Unit tests for configuration settings."""

import allure
import pytest
from pydantic import ValidationError
from pytest import MonkeyPatch

from src.utils.config import Settings


FEATURE = "Configuration"
STORY = "Settings Validation"
LIFECYCLE_STORY = "Settings Lifecycle"
pytestmark = [pytest.mark.unit]


class TestSettingsWebhookCallbackUrl:
    """Test webhook_callback_url field validation."""

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-001")
    @allure.label("level", "Unit")
    @allure.label("priority", "P1")
    @allure.severity(allure.severity_level.NORMAL)
    def test_default_value(self, monkeypatch: MonkeyPatch) -> None:
        """Test that default value is set correctly for development."""
        # Clear environment variable to ensure default is used
        monkeypatch.delenv("WEBHOOK_CALLBACK_URL", raising=False)
        settings = Settings()
        assert settings.webhook_callback_url == "http://localhost:8000/webhook/youtube"

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-002")
    @allure.label("level", "Unit")
    @allure.label("priority", "P0")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_load_from_environment(self, monkeypatch: MonkeyPatch) -> None:
        """Test loading webhook_callback_url from environment variable."""
        test_url = "https://example.com/webhook/youtube"
        monkeypatch.setenv("WEBHOOK_CALLBACK_URL", test_url)
        settings = Settings()
        assert settings.webhook_callback_url == test_url

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-003")
    @allure.label("level", "Unit")
    @allure.label("priority", "P0")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_https_production_url_accepted(self, monkeypatch: MonkeyPatch) -> None:
        """Test that HTTPS URLs for production are accepted."""
        test_url = "https://youtube-bot.nmro.cc/webhook/youtube"
        monkeypatch.setenv("WEBHOOK_CALLBACK_URL", test_url)
        settings = Settings()
        assert settings.webhook_callback_url == test_url

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-004")
    @allure.label("level", "Unit")
    @allure.label("priority", "P1")
    @allure.severity(allure.severity_level.NORMAL)
    def test_localhost_http_accepted(self, monkeypatch: MonkeyPatch) -> None:
        """Test that localhost HTTP URLs are accepted for development."""
        test_urls = [
            "http://localhost:8000/webhook/youtube",
            "http://localhost:3000/webhook/youtube",
            "http://localhost/webhook/youtube",
        ]
        for url in test_urls:
            monkeypatch.setenv("WEBHOOK_CALLBACK_URL", url)
            settings = Settings()
            assert settings.webhook_callback_url == url

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-005")
    @allure.label("level", "Unit")
    @allure.label("priority", "P0")
    @allure.severity(allure.severity_level.BLOCKER)
    def test_http_production_url_rejected(self, monkeypatch: MonkeyPatch) -> None:
        """Test that HTTP URLs for production (non-localhost) are rejected."""
        invalid_urls = [
            "http://example.com/webhook/youtube",
            "http://youtube-bot.nmro.cc/webhook/youtube",
            "http://192.168.1.1/webhook/youtube",
        ]
        for url in invalid_urls:
            monkeypatch.setenv("WEBHOOK_CALLBACK_URL", url)
            with pytest.raises(ValidationError) as exc_info:
                Settings()
            assert "Production webhook callback URL must use HTTPS" in str(exc_info.value)

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-006")
    @allure.label("level", "Unit")
    @allure.label("priority", "P1")
    @allure.severity(allure.severity_level.NORMAL)
    def test_https_validation_error_message(self, monkeypatch: MonkeyPatch) -> None:
        """Test that validation error message is clear and helpful."""
        monkeypatch.setenv("WEBHOOK_CALLBACK_URL", "http://example.com/webhook/youtube")
        with pytest.raises(ValidationError) as exc_info:
            Settings()
        error_message = str(exc_info.value)
        assert "HTTPS" in error_message
        assert "localhost" in error_message

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.1-UNIT-007")
    @allure.label("level", "Unit")
    @allure.label("priority", "P1")
    @allure.severity(allure.severity_level.NORMAL)
    def test_custom_localhost_port(self, monkeypatch: MonkeyPatch) -> None:
        """Test that localhost with custom ports works."""
        test_url = "http://localhost:9000/custom/path"
        monkeypatch.setenv("WEBHOOK_CALLBACK_URL", test_url)
        settings = Settings()
        assert settings.webhook_callback_url == test_url


class TestSettingsIntegration:
    """Integration tests for Settings class."""

    @allure.feature(FEATURE)
    @allure.story(LIFECYCLE_STORY)
    @allure.label("test_id", "1.1-UNIT-008")
    @allure.label("level", "Unit")
    @allure.label("priority", "P1")
    @allure.severity(allure.severity_level.NORMAL)
    def test_settings_singleton_behavior(self) -> None:
        """Test that settings maintains consistent values."""
        from src.utils.config import settings as settings1
        from src.utils.config import settings as settings2

        assert settings1.webhook_callback_url == settings2.webhook_callback_url

    @allure.feature(FEATURE)
    @allure.story(LIFECYCLE_STORY)
    @allure.label("test_id", "1.1-UNIT-009")
    @allure.label("level", "Unit")
    @allure.label("priority", "P0")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_all_required_fields_present(self, monkeypatch: MonkeyPatch) -> None:
        """Test that all required configuration fields are accessible."""
        # Set required environment variables
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "test_token")
        monkeypatch.setenv("YOUTUBE_API_KEY", "test_key")
        monkeypatch.setenv("WEBHOOK_CALLBACK_URL", "http://localhost:8000/webhook/youtube")

        settings = Settings()

        # Test that all fields are accessible
        assert hasattr(settings, "telegram_bot_token")
        assert hasattr(settings, "youtube_api_key")
        assert hasattr(settings, "webhook_callback_url")
        assert hasattr(settings, "database_url")
        assert hasattr(settings, "webhook_host")
        assert hasattr(settings, "webhook_port")
        assert hasattr(settings, "webhook_path")
        assert hasattr(settings, "log_level")


class TestSettingsLocalization:
    """Tests for localization-related settings."""

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.14-UNIT-LOC-001")
    @allure.label("priority", "P1")
    @pytest.mark.unit
    def test_default_locale_env_is_normalized(self, monkeypatch: MonkeyPatch) -> None:
        """DEFAULT_LOCALE should be case-insensitive and validated."""
        monkeypatch.setenv("DEFAULT_LOCALE", "RU")
        settings_obj = Settings()
        assert settings_obj.default_locale == "ru"

    @allure.feature(FEATURE)
    @allure.story(STORY)
    @allure.label("test_id", "1.14-UNIT-LOC-002")
    @allure.label("priority", "P1")
    @pytest.mark.unit
    def test_default_locale_invalid_value(self, monkeypatch: MonkeyPatch) -> None:
        """Unsupported locale values should raise validation errors."""
        monkeypatch.setenv("DEFAULT_LOCALE", "jp")
        with pytest.raises(ValidationError):
            Settings()
        # Reset to a known good locale and confirm the config object still exposes pubsub settings.
        monkeypatch.setenv("DEFAULT_LOCALE", "en")
        validated_settings = Settings()
        assert hasattr(validated_settings, "pubsub_lease_renewal_interval")
        assert hasattr(validated_settings, "pubsub_lease_renewal_threshold")
        assert hasattr(validated_settings, "pubsub_lease_renewal_batch_limit")


class TestPubSubLeaseRenewal:
    """Tests for PubSub lease renewal."""

    @allure.feature(FEATURE)
    @allure.story(LIFECYCLE_STORY)
    @allure.label("test_id", "1.1-UNIT-010")
    @allure.label("level", "Unit")
    @allure.label("priority", "P1")
    @allure.severity(allure.severity_level.NORMAL)
    def test_pubsub_settings_defaults(self, monkeypatch: MonkeyPatch) -> None:
        """PubSub lease renewal settings should expose sane defaults."""
        monkeypatch.delenv("PUBSUB_LEASE_RENEWAL_INTERVAL", raising=False)
        monkeypatch.delenv("PUBSUB_LEASE_RENEWAL_THRESHOLD", raising=False)
        monkeypatch.delenv("PUBSUB_LEASE_RENEWAL_BATCH_LIMIT", raising=False)

        settings = Settings()
        assert settings.pubsub_lease_renewal_interval == 3600
        assert settings.pubsub_lease_renewal_threshold == 21_600
        assert settings.pubsub_lease_renewal_batch_limit == 50

    @allure.feature(FEATURE)
    @allure.story(LIFECYCLE_STORY)
    @allure.label("test_id", "1.1-UNIT-011")
    @allure.label("level", "Unit")
    @allure.label("priority", "P0")
    @allure.severity(allure.severity_level.CRITICAL)
    def test_pubsub_settings_validation(self, monkeypatch: MonkeyPatch) -> None:
        """Negative intervals or batch sizes should be rejected."""
        monkeypatch.setenv("PUBSUB_LEASE_RENEWAL_INTERVAL", "-5")
        with pytest.raises(ValidationError):
            Settings()

        monkeypatch.setenv("PUBSUB_LEASE_RENEWAL_INTERVAL", "300")
        monkeypatch.setenv("PUBSUB_LEASE_RENEWAL_THRESHOLD", "0")
        with pytest.raises(ValidationError):
            Settings()

        monkeypatch.setenv("PUBSUB_LEASE_RENEWAL_THRESHOLD", "600")
        monkeypatch.setenv("PUBSUB_LEASE_RENEWAL_BATCH_LIMIT", "0")
        with pytest.raises(ValidationError):
            Settings()
