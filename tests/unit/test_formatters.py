"""Unit tests for formatting helpers."""

from types import SimpleNamespace

import pytest

from src.utils.formatters import format_group_discussion_prompt, format_subscription_list


def _subscription(channel_name: str, channel_url: str):
    channel = SimpleNamespace(channel_name=channel_name, channel_url=channel_url)
    return SimpleNamespace(channel=channel)


def test_format_subscription_list_private_locale_en():
    """Subscription list should include translated header and footer."""
    subscriptions = [
        _subscription("Test Channel", "https://youtube.com/@test"),
    ]
    output = format_subscription_list(
        subscriptions,
        chat_title=None,
        chat_type="private",
        locale="en",
        request_id="fmt-1",
    )
    assert "📋 Your subscriptions" in output
    assert "Use /unsubscribe" in output
    assert "Test Channel" in output


def test_format_subscription_list_group_without_title_uses_fallback():
    """Unnamed group chats should use localized fallback label."""
    subscriptions = [
        _subscription("Channel A", "https://youtube.com/@a"),
    ]
    output = format_subscription_list(
        subscriptions,
        chat_title=None,
        chat_type="group",
        locale="de",
        request_id="fmt-2",
    )
    assert "diesem Chat" in output


@pytest.mark.parametrize(
    ("chat_type", "expected_phrase"),
    [
        ("channel", "📣"),
        ("group", "💬"),
    ],
)
def test_format_group_discussion_prompt_translated(chat_type: str, expected_phrase: str):
    """Group prompts should be localized and include fallback labels."""
    prompt = format_group_discussion_prompt(
        chat_type=chat_type,
        chat_title=None,
        locale="ru",
        request_id="fmt-3",
    )
    assert prompt is not None
    assert expected_phrase in prompt


def test_escape_markdown_v2():
    """Test escaping of MarkdownV2 special characters."""
    from src.utils.formatters import escape_markdown_v2

    escape_chars = "_*[]()~`>#+-=|{}.!"
    for char in escape_chars:
        text = f"char is {char}"
        expected = f"char is \\{char}"
        assert escape_markdown_v2(text) == expected

    text = "Hello, world! This is a test."
    expected = "Hello, world\\! This is a test\\."
    assert escape_markdown_v2(text) == expected

    text = "No special characters here"
    assert escape_markdown_v2(text) == text
