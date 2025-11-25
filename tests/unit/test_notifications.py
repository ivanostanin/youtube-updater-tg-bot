"""Unit tests for notification helpers."""

from datetime import UTC, datetime
from types import SimpleNamespace

from telegramify_markdown import markdownify

from src.bot.notifications import NotificationService


def _build_video():
    return SimpleNamespace(
        title="Test Video Title",
        description="Detailed description",
        url="https://youtube.com/watch?v=abc",
        published_at=datetime(2024, 12, 1, 12, 30, tzinfo=UTC),
        video_id="abc",
    )


def _build_channel():
    return SimpleNamespace(
        channel_name="Test Channel",
        channel_id="UC123",
        channel_url="https://youtube.com/@test",
    )


async def test_format_video_message_includes_translated_labels():
    """Notification body should include localized labels."""
    service = NotificationService(bot=SimpleNamespace())
    message = service.format_video_message(
        video=_build_video(),
        channel=_build_channel(),
        chat_title="Test Chat",
        chat_type="group",
        locale="en",
        request_id="notif-1",
    )
    assert markdownify("🎬 **New Video Alert!**") in message
    assert markdownify("📺 **Channel:** Test Channel") in message
    assert "💬" in message  # group prompt
