"""Unit tests for localization helper."""

import pytest

from src.utils.i18n import i18n, translate


@pytest.fixture(autouse=True)
def reset_i18n_cache():
    """Ensure catalogs and warning caches are reset around each test."""
    i18n.reset()
    yield
    i18n.reset()


def test_translate_returns_english_default():
    """English catalog should return expected string."""
    text = translate("handlers.subscribe.processing", locale="en", request_id="test")
    assert text == "🔍 Processing YouTube URL..."


def test_translate_falls_back_to_english_for_unknown_locale():
    """Unsupported locales should gracefully fall back to English."""
    text = translate("handlers.subscribe.processing", locale="fr", request_id="test")
    assert text == "🔍 Processing YouTube URL..."


def test_translate_applies_formatting_placeholders():
    """Translation placeholders should be interpolated safely."""
    rendered = translate(
        "handlers.subscribe.video.already_subscribed",
        locale="en",
        request_id="req-123",
        channel_name="Test Channel",
        video_title="Test Video",
    )
    assert "Test Channel" in rendered
    assert "Test Video" in rendered
