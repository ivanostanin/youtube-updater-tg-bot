"""Unit tests for bot command handlers.

Tests cover all command handlers including /start, /help, /subscribe, /list,
/unsubscribe, callback query handling, and YouTube URL processing.
"""

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from sqlalchemy import select
from telegram import CallbackQuery, InlineKeyboardMarkup
from telegram.error import TelegramError

from src.bot.handlers import BotHandlers, CommandExecutionContext
from src.database.models import ChannelAdminLink, Chat, Subscription, User, YouTubeChannel
from src.database.repository import SubscriptionRepository, UserRepository
from src.services import ACLService
from src.utils.config import settings


@allure.feature("Bot Handlers")
@allure.story("Start Command")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_start_command_creates_user(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Test /start command creates user in database.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.start_command(mock_telegram_update, mock_telegram_context)

    # Verify user was created
    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_user_by_telegram_id("123456789")
    assert db_user is not None
    assert db_user.username == "testuser"
    assert db_user.first_name == "Test"

    # Verify welcome message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "Welcome to YouTube Updater Bot" in call_args
    assert "/subscribe" in call_args


@allure.feature("Bot Handlers")
@allure.story("Help Command")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_help_command(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Test /help command returns help text.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.help_command(mock_telegram_update, mock_telegram_context)

    # Verify help message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "YouTube Updater Bot Commands" in call_args
    assert "/subscribe" in call_args
    assert "/list" in call_args
    assert "/unsubscribe" in call_args
    assert "youtube.com/@username" in call_args


@allure.feature("Bot Handlers")
@allure.story("Subscribe Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscribe_command_without_url(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Test /subscribe command without URL shows error message.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_context.args = []

    await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify error message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "Please provide a YouTube URL" in call_args
    assert "Example:" in call_args


@allure.feature("Bot Handlers")
@allure.story("Subscribe Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscribe_command_with_valid_url(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Test /subscribe command with valid URL processes the URL.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_context.args = ["https://youtube.com/@testchannel"]

    # Mock handle_youtube_url to verify it was called
    handlers.handle_youtube_url = AsyncMock()

    await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify handle_youtube_url was called with the URL
    handlers.handle_youtube_url.assert_called_once()
    call_args, call_kwargs = handlers.handle_youtube_url.call_args
    assert call_args[:3] == (
        mock_telegram_update,
        mock_telegram_context,
        "https://youtube.com/@testchannel",
    )
    assert call_kwargs.get("request_id")


@allure.feature("Bot Handlers")
@allure.story("List Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_list_command_no_subscriptions(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Test /list command with no subscriptions.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    # Create user without subscriptions
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.commit()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.list_command(mock_telegram_update, mock_telegram_context)

    # Verify message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "don't have any active subscriptions" in call_args


@allure.feature("Bot Handlers")
@allure.story("List Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_list_command_with_subscriptions(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Test /list command with active subscriptions.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    # Create user, chat, channel, and subscription
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title=mock_telegram_update.effective_chat.username,
    )
    async_db_session.add(chat)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.list_command(mock_telegram_update, mock_telegram_context)

    # Verify subscription list was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "Your subscriptions:" in call_args
    assert "Test Channel" in call_args
    assert "UCtest123" in call_args


@allure.feature("Bot Handlers")
@allure.story("List Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_list_command_creates_user_for_group_admin(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Group admins without prior DM history should still be able to list subscriptions."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.acl_service.require_admin = AsyncMock(return_value=True)

    mock_telegram_update.effective_chat.type = "supergroup"
    mock_telegram_update.message.chat.type = "supergroup"
    mock_telegram_update.effective_chat.username = "testgroup"
    mock_telegram_update.message.chat.username = "testgroup"

    chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title="Test Group",
    )
    async_db_session.add(chat)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.list_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "Test Channel" in call_args

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_user_by_telegram_id("123456789")
    assert db_user is not None


@allure.feature("Bot Handlers")
@allure.story("Unsubscribe Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_command_no_subscriptions(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Test /unsubscribe command with no subscriptions.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    # Create user without subscriptions
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.commit()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.unsubscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "don't have any active subscriptions" in call_args


@allure.feature("Bot Handlers")
@allure.story("Unsubscribe Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_command_with_subscriptions(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Test /unsubscribe command shows inline keyboard with subscriptions.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    # Create user, chat, channel, and subscription
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title=mock_telegram_update.effective_chat.username,
    )
    async_db_session.add(chat)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.unsubscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify inline keyboard was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args
    assert "Select a subscription to remove:" in call_args[0][0]
    assert "reply_markup" in call_args[1]
    reply_markup = call_args[1]["reply_markup"]
    assert isinstance(reply_markup, InlineKeyboardMarkup)


@allure.feature("Bot Handlers")
@allure.story("Access Control")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_list_command_requires_admin_in_group_chat(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Group chats must pass admin verification before listing subscriptions."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.effective_chat.type = "supergroup"

    async def fake_require_admin(**kwargs):
        await kwargs["on_denied"]("Only chat administrators can run /list.")
        return False

    handlers.acl_service = MagicMock()
    handlers.acl_service.require_admin = AsyncMock(side_effect=fake_require_admin)

    with patch("src.bot.handlers.AsyncSessionLocal") as mock_session:
        await handlers.list_command(mock_telegram_update, mock_telegram_context)

    mock_session.assert_not_called()
    mock_telegram_update.message.reply_text.assert_called_once_with(
        "Only chat administrators can run /list."
    )


@allure.feature("Bot Handlers")
@allure.story("Callback Queries")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_handle_unsubscribe_callback_cancel(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Test unsubscribe callback with cancel action.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    # Setup callback query
    query = MagicMock(spec=CallbackQuery)
    query.data = "cancel"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    mock_telegram_update.callback_query = query

    await handlers.handle_unsubscribe_callback(mock_telegram_update, mock_telegram_context)

    # Verify callback was answered and message edited
    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once_with("Cancelled.", parse_mode="MarkdownV2")


@allure.feature("Bot Handlers")
@allure.story("Callback Queries")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_handle_unsubscribe_callback_success(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, async_db_session
):
    """Test unsubscribe callback successfully removes subscription.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)
    handlers.check_if_channel_has_other_subscribers = AsyncMock(return_value=False)

    # Create user, chat, channel, and subscription
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title=mock_telegram_update.effective_chat.username,
    )
    async_db_session.add(chat)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()

    # Setup callback query
    query = MagicMock(spec=CallbackQuery)
    query.data = f"unsub_{channel.id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    mock_telegram_update.callback_query = query

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.handle_unsubscribe_callback(mock_telegram_update, mock_telegram_context)

    # Verify callback was answered and success message shown
    query.answer.assert_called_once()
    assert query.edit_message_text.call_count >= 1
    last_call = query.edit_message_text.call_args[0][0]
    assert "Subscription removed successfully" in last_call


@allure.feature("Bot Handlers")
@allure.story("Access Control")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_handle_unsubscribe_callback_denies_non_admin(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Non-admin users should be blocked from callback unsubscriptions in group chats."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.effective_chat.type = "supergroup"

    query = MagicMock(spec=CallbackQuery)
    query.data = "unsub_1"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.message.chat = mock_telegram_update.effective_chat
    mock_telegram_update.callback_query = query

    async def fake_require_admin(**kwargs):
        await kwargs["on_denied"]("Only admins can remove subscriptions.")
        return False

    handlers.acl_service = MagicMock()
    handlers.acl_service.require_admin = AsyncMock(side_effect=fake_require_admin)

    with patch("src.bot.handlers.AsyncSessionLocal") as mock_session:
        await handlers.handle_unsubscribe_callback(mock_telegram_update, mock_telegram_context)

    mock_session.assert_not_called()
    query.answer.assert_awaited_once_with("Only admins can remove subscriptions.", show_alert=True)
    query.edit_message_text.assert_not_called()


@allure.feature("Bot Handlers")
@allure.story("Message Handler")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_handle_message_with_youtube_url(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Test message handler processes YouTube URLs.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.handle_youtube_url = AsyncMock()

    mock_telegram_update.message.text = "Check this out: https://youtube.com/@testchannel"

    await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    # Verify handle_youtube_url was called
    handlers.handle_youtube_url.assert_called_once()
    call_args = handlers.handle_youtube_url.call_args[0]
    assert "youtube.com" in call_args[2]


@allure.feature("Bot Handlers")
@allure.story("Access Control")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_handle_youtube_url_denies_non_admin_group(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Group members without admin rights cannot add subscriptions."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.effective_chat.type = "supergroup"
    mock_telegram_update.message.reply_text = AsyncMock()
    mock_youtube_api.resolve_url = AsyncMock()

    async def fake_require_admin(**kwargs):
        await kwargs["on_denied"]("Only admins can subscribe this chat.")
        return False

    handlers.acl_service = MagicMock()
    handlers.acl_service.require_admin = AsyncMock(side_effect=fake_require_admin)

    await handlers.handle_youtube_url(
        mock_telegram_update, mock_telegram_context, "https://youtube.com/@demo"
    )

    mock_youtube_api.resolve_url.assert_not_called()
    mock_telegram_update.message.reply_text.assert_called_once_with(
        "Only admins can subscribe this chat."
    )


@allure.feature("Bot Handlers")
@allure.story("Message Handler")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_handle_message_without_youtube_url(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Test message handler with non-YouTube text.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    mock_telegram_update.message.text = "Hello bot, how are you?"

    await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    # Verify help message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "Send me a YouTube URL" in call_args


@allure.feature("Bot Handlers")
@allure.story("Logging")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_subscribe_command_logs_context(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, caplog
):
    """Subscribe command emits structured logging context."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.handle_youtube_url = AsyncMock()
    mock_telegram_context.args = ["https://youtube.com/@demo"]
    caplog.set_level(logging.DEBUG)

    await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    records = [
        record
        for record in caplog.records
        if getattr(record, "operation", None) == "handler.subscribe"
        and getattr(record, "meta_url_preview", None)
    ]
    assert records, "Expected handler.subscribe log entry"
    record = records[0]
    assert record.chat_id == str(mock_telegram_update.effective_chat.id)
    assert record.user_id == str(mock_telegram_update.effective_user.id)
    assert getattr(record, "request_id", None)


@allure.feature("Bot Handlers")
@allure.story("Logging")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_handle_message_logs_context(
    mock_telegram_update, mock_telegram_context, mock_youtube_api, caplog
):
    """handle_message emits debug log with chat/user/request identifiers."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.handle_youtube_url = AsyncMock()
    mock_telegram_update.message.text = "Watch https://youtube.com/@context"
    caplog.set_level(logging.DEBUG)

    await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    records = [
        record
        for record in caplog.records
        if getattr(record, "operation", None) == "handler.message"
        and getattr(record, "meta_url_preview", None)
    ]
    assert records, "Expected handler.message log entry"
    record = records[0]
    assert record.chat_id == str(mock_telegram_update.effective_chat.id)
    assert record.user_id == str(mock_telegram_update.effective_user.id)
    assert getattr(record, "request_id", None)


@allure.feature("Bot Handlers")
@allure.story("Message Handler")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_handle_message_ignores_non_youtube_group_text(
    mock_telegram_update, mock_telegram_context, mock_youtube_api
):
    """Ensure the bot does not spam group chats for non-YouTube messages."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    mock_telegram_update.effective_chat.type = "supergroup"
    mock_telegram_update.message.chat.type = "supergroup"
    mock_telegram_update.message.text = "Just chatting here."
    mock_telegram_update.message.reply_text.reset_mock()

    await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_not_called()


@allure.feature("Bot Handlers")
@allure.story("Webhook Management")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_manage_channel_webhook_subscribe(
    mock_youtube_api, mock_pubsub_manager, mock_telegram_bot
):
    """Test webhook management for subscribing to a channel.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        mock_pubsub_manager: Mock PubSubManager fixture.
        mock_telegram_bot: Mock Telegram bot fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_bot)
    handlers.webhook_manager = mock_pubsub_manager
    mock_pubsub_manager.subscribe_to_channel = AsyncMock(return_value=True)

    result = await handlers.manage_channel_webhook("UCtest123", "subscribe")

    # Verify webhook subscription was called
    mock_pubsub_manager.subscribe_to_channel.assert_called_once_with("UCtest123")
    assert result is True


@allure.feature("Bot Handlers")
@allure.story("Webhook Management")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_manage_channel_webhook_unsubscribe(
    mock_youtube_api, mock_pubsub_manager, mock_telegram_bot
):
    """Test webhook management for unsubscribing from a channel.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        mock_pubsub_manager: Mock PubSubManager fixture.
        mock_telegram_bot: Mock Telegram bot fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_bot)
    handlers.webhook_manager = mock_pubsub_manager
    mock_pubsub_manager.unsubscribe_from_channel = AsyncMock(return_value=True)

    result = await handlers.manage_channel_webhook("UCtest123", "unsubscribe")

    # Verify webhook unsubscription was called
    mock_pubsub_manager.unsubscribe_from_channel.assert_called_once_with("UCtest123")
    assert result is True


@allure.feature("Bot Handlers")
@allure.story("Webhook Management")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_manage_channel_webhook_error_handling(
    mock_youtube_api, mock_pubsub_manager, mock_telegram_bot
):
    """Test webhook management handles errors gracefully.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        mock_pubsub_manager: Mock PubSubManager fixture.
        mock_telegram_bot: Mock Telegram bot fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_bot)
    handlers.webhook_manager = mock_pubsub_manager
    mock_pubsub_manager.subscribe_to_channel = AsyncMock(side_effect=Exception("Network error"))

    result = await handlers.manage_channel_webhook("UCtest123", "subscribe")

    # Verify error was handled
    assert result is False


@allure.feature("Bot Handlers")
@allure.story("Webhook Management")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscribe_sets_channel_webhook(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure the channel stores the callback URL after initial subscription."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)
    handlers.check_if_channel_has_other_subscribers = AsyncMock(return_value=False)

    mock_youtube_api.resolve_url = AsyncMock(
        return_value={
            "id": "UCtest123",
            "title": "Test Channel",
            "url": "https://youtube.com/channel/UCtest123",
        }
    )
    mock_youtube_api.get_feed_url = MagicMock(
        return_value="https://youtube.com/feeds/videos.xml?channel_id=UCtest123"
    )

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.handle_youtube_url(
            mock_telegram_update,
            mock_telegram_context,
            "https://youtube.com/@testchannel",
        )

    subscription_rows = await async_db_session.execute(select(Subscription))
    subscription = subscription_rows.scalar_one()
    assert subscription.webhook_url == settings.webhook_callback_url


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_normalize_channel_identifier_preserves_invite_link():
    """Invite links should remain intact so Telegram accepts the lookup."""
    identifier = BotHandlers._normalize_channel_identifier("https://t.me/+SecretToken?start=foo")
    assert identifier == "+SecretToken"


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_normalize_channel_identifier_accepts_plus_token_without_at():
    """Bare +tokens should not be rewritten into @usernames."""
    identifier = BotHandlers._normalize_channel_identifier("+AnotherSecretToken")
    assert identifier == "+AnotherSecretToken"


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_channel_identifier_candidates_include_invite_variants():
    """Invite links should try token, canonical https, and raw input."""
    candidates = BotHandlers._channel_identifier_candidates(" https://telegram.me/+SecretToken ")
    assert candidates[0] == "+SecretToken"
    assert "https://t.me/+SecretToken" in candidates
    assert "https://telegram.me/+SecretToken" in candidates


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_link_command_links_channel(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure /channel_link persists channel-admin metadata and activates context."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_context.args = ["@examplechannel"]

    channel_chat = MagicMock()
    channel_chat.id = -100987654321
    channel_chat.type = "channel"
    channel_chat.title = "Example Channel"
    channel_chat.username = "examplechannel"

    admin_member = MagicMock()
    admin_member.status = "administrator"
    bot_member = MagicMock()
    bot_member.can_post_messages = True
    bot_member.can_delete_messages = True
    bot_member.can_edit_messages = True

    mock_telegram_context.bot.get_chat = AsyncMock(return_value=channel_chat)
    mock_telegram_context.bot.get_chat_member = AsyncMock(side_effect=[admin_member, bot_member])

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.channel_link_command(mock_telegram_update, mock_telegram_context)

    link_rows = await async_db_session.execute(select(ChannelAdminLink))
    link = link_rows.scalar_one()
    assert link.channel_chat_id is not None
    assert link.admin_user_id is not None
    assert link.revoked_at is None

    chat_rows = await async_db_session.execute(select(Chat))
    chats = chat_rows.scalars().all()
    private_chat = next(chat for chat in chats if chat.chat_type == "private")
    linked_channel = next(chat for chat in chats if chat.chat_type == "channel")

    assert private_chat.active_channel_chat_id == linked_channel.id
    reply_text = mock_telegram_update.message.reply_text.call_args.args[0]
    assert "Example Channel" in reply_text


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_link_command_invite_link_retries_lookup(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Invite-link lookups should retry with alternate identifiers before failing."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_context.args = ["https://t.me/+SecretToken"]

    channel_chat = MagicMock()
    channel_chat.id = -100333222111
    channel_chat.type = "channel"
    channel_chat.title = "Secret Channel"

    admin_member = MagicMock()
    admin_member.status = "administrator"
    bot_member = MagicMock()
    bot_member.can_post_messages = True
    bot_member.can_delete_messages = True
    bot_member.can_edit_messages = True

    mock_telegram_context.bot.get_chat = AsyncMock(
        side_effect=[TelegramError("Chat not found"), channel_chat]
    )
    mock_telegram_context.bot.get_chat_member = AsyncMock(side_effect=[admin_member, bot_member])

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.channel_link_command(mock_telegram_update, mock_telegram_context)

    # ensure fallback lookup order
    assert mock_telegram_context.bot.get_chat.await_args_list[0].args == ("+SecretToken",)
    assert mock_telegram_context.bot.get_chat.await_args_list[1].args == (
        "https://t.me/+SecretToken",
    )

    link_rows = await async_db_session.execute(select(ChannelAdminLink))
    link = link_rows.scalar_one()
    assert link.channel_chat_id is not None
    assert link.admin_user_id is not None


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_dm_subscription_targets_channel_context(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure DM subscriptions use the selected channel chat."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)
    handlers.check_if_channel_has_other_subscribers = AsyncMock(return_value=True)
    verify_patch = AsyncMock(return_value=(True, []))
    mock_acl = MagicMock(spec=ACLService)
    mock_acl.verify_admin = AsyncMock(return_value=True)
    handlers.acl_service = mock_acl
    handlers._verify_bot_permissions = verify_patch

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="dmuser",
        first_name="DM",
        last_name="User",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channel_chat = Chat(
        chat_id="-100111222333",
        chat_type="channel",
        title="DM Channel",
    )
    async_db_session.add_all([actor_chat, channel_chat])
    await async_db_session.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    actor_chat.active_channel_chat_id = channel_chat.id
    actor_chat.active_channel_selected_at = now
    actor_chat.active_channel_expires_at = now + timedelta(minutes=60)
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel_chat.id,
            admin_user_id=db_user.id,
            role="administrator",
        )
    )
    await async_db_session.commit()

    mock_youtube_api.resolve_url = AsyncMock(
        return_value={
            "id": "UCtest999",
            "title": "Test Channel",
            "url": "https://youtube.com/channel/UCtest999",
        }
    )
    mock_youtube_api.get_feed_url = MagicMock(
        return_value="https://youtube.com/feeds/videos.xml?channel_id=UCtest999"
    )

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        mock_telegram_context.args = ["https://youtube.com/@testchannel"]
        await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    subscription_rows = await async_db_session.execute(select(Subscription))
    subscription = subscription_rows.scalar_one()
    channel_chats = await async_db_session.execute(select(Chat).where(Chat.chat_type == "channel"))
    channel_chat_row = channel_chats.scalars().first()
    assert channel_chat_row is not None
    assert subscription.chat_id == channel_chat_row.id


@allure.feature("Bot Handlers")
@allure.story("Channel Linking")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_channel_link_command_links_private_channel_via_forward(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Allow linking when the admin replies to a forwarded private channel message."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_context.args = []

    forward_channel = MagicMock()
    forward_channel.id = -100777888999
    forward_channel.type = "channel"
    forward_channel.title = "Private Channel"
    forward_channel.username = None

    message = SimpleNamespace(
        reply_text=AsyncMock(),
        chat=mock_telegram_update.effective_chat,
        from_user=mock_telegram_update.effective_user,
        text="/channel_link",
    )
    message.forward_origin = SimpleNamespace(chat=forward_channel)
    mock_telegram_update.message = message
    mock_telegram_update.effective_message = message

    admin_member = MagicMock()
    admin_member.status = "administrator"
    bot_member = MagicMock()
    bot_member.can_post_messages = True
    bot_member.can_delete_messages = True
    bot_member.can_edit_messages = True

    mock_telegram_context.bot.get_chat_member = AsyncMock(side_effect=[admin_member, bot_member])
    mock_telegram_context.bot.get_chat = AsyncMock()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.channel_link_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_context.bot.get_chat.assert_not_called()

    link_rows = await async_db_session.execute(select(ChannelAdminLink))
    link = link_rows.scalar_one()
    assert link.revoked_at is None


@allure.feature("Bot Handlers")
@allure.story("Channel Unlink")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_channel_unlink_command_requires_channel_context(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure /channel_unlink warns when no channel context is active."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.message.reply_text.reset_mock()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.channel_unlink_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called_once()
    reply_text = mock_telegram_update.message.reply_text.call_args.args[0]
    assert "/channel_select" in reply_text


@allure.feature("Bot Handlers")
@allure.story("Unsubscribe Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_command_stops_when_context_cleared(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure /unsubscribe aborts when channel context is revoked/expired."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="contextless",
        first_name="Context",
        last_name="Less",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    async_db_session.add(actor_chat)
    await async_db_session.commit()

    context_state = CommandExecutionContext(
        db_user=db_user,
        actor_chat=actor_chat,
        target_chat=actor_chat,
        locale="en",
        context_cleared=True,
        context_message_key="handlers.channel_context.expired",
        context_message_params={"channel_title": "Sample Channel"},
    )

    mock_get_subs = AsyncMock()
    mock_telegram_update.message.reply_text.reset_mock()

    with (
        patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session),
        patch.object(
            handlers,
            "_build_command_context",
            AsyncMock(return_value=context_state),
        ),
        patch.object(
            SubscriptionRepository,
            "get_chat_subscriptions",
            mock_get_subs,
        ),
    ):
        await handlers.unsubscribe_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called_once()
    assert "expired" in mock_telegram_update.message.reply_text.call_args.args[0]
    assert mock_get_subs.await_count == 0


@allure.feature("Bot Handlers")
@allure.story("Channel Unlink")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_unlink_command_prompts_confirmation(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """DM unlink command should render a confirmation keyboard and summary."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="unlinker",
        first_name="Unlink",
        last_name="User",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channel_chat = Chat(
        chat_id="-10099887766",
        chat_type="channel",
        title="Channel To Remove",
    )
    async_db_session.add_all([actor_chat, channel_chat])
    await async_db_session.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    actor_chat.active_channel_chat_id = channel_chat.id
    actor_chat.active_channel_selected_at = now
    actor_chat.active_channel_expires_at = now + timedelta(minutes=30)
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel_chat.id,
            admin_user_id=db_user.id,
            role="administrator",
        )
    )
    youtube_channel = YouTubeChannel(
        channel_id="UCunlink",
        channel_name="To Unlink",
        channel_url="https://youtube.com/channel/UCunlink",
    )
    async_db_session.add(youtube_channel)
    await async_db_session.flush()
    async_db_session.add(
        Subscription(
            chat_id=channel_chat.id,
            channel_id=youtube_channel.id,
            is_active=True,
        )
    )
    await async_db_session.commit()
    mock_telegram_update.message.reply_text.reset_mock()

    context_state = CommandExecutionContext(
        db_user=db_user,
        actor_chat=actor_chat,
        target_chat=channel_chat,
        locale="en",
    )
    with (
        patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session),
        patch.object(
            handlers,
            "_build_command_context",
            AsyncMock(return_value=context_state),
        ),
    ):
        await handlers.channel_unlink_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called_once()
    args, kwargs = mock_telegram_update.message.reply_text.call_args
    assert "Channel To Remove" in args[0]
    assert "1" in args[0]
    keyboard = kwargs["reply_markup"]
    confirm_button = keyboard.inline_keyboard[0][0]
    assert confirm_button.callback_data == f"chanunlink::confirm::{channel_chat.id}"


@allure.feature("Bot Handlers")
@allure.story("Channel Unlink")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_unlink_callback_cleans_up_channel(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Confirming unlink should revoke links, disable subscriptions, and clean up webhooks."""
    mock_acl = MagicMock(spec=ACLService)
    mock_acl.verify_admin = AsyncMock(return_value=True)
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot, acl_service=mock_acl)

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="cleanup",
        first_name="Clean",
        last_name="Up",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channel_chat = Chat(
        chat_id="-10011223344",
        chat_type="channel",
        title="Cleanup Channel",
    )
    async_db_session.add_all([actor_chat, channel_chat])
    await async_db_session.flush()
    now = datetime.now(UTC).replace(tzinfo=None)
    actor_chat.active_channel_chat_id = channel_chat.id
    actor_chat.active_channel_selected_at = now
    actor_chat.active_channel_expires_at = now + timedelta(minutes=30)
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel_chat.id,
            admin_user_id=db_user.id,
            role="administrator",
        )
    )

    youtube_channels = [
        YouTubeChannel(
            channel_id="UCunlink1",
            channel_name="First Channel",
            channel_url="https://youtube.com/channel/UCunlink1",
        ),
        YouTubeChannel(
            channel_id="UCunlink2",
            channel_name="Second Channel",
            channel_url="https://youtube.com/channel/UCunlink2",
        ),
    ]
    async_db_session.add_all(youtube_channels)
    await async_db_session.flush()
    async_db_session.add_all(
        [
            Subscription(
                chat_id=channel_chat.id, channel_id=youtube_channels[0].id, is_active=True
            ),
            Subscription(
                chat_id=channel_chat.id, channel_id=youtube_channels[1].id, is_active=True
            ),
        ]
    )
    await async_db_session.commit()

    query = MagicMock()
    query.data = f"chanunlink::confirm::{channel_chat.id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = SimpleNamespace()
    mock_telegram_update.callback_query = query

    with (
        patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session),
        patch.object(
            handlers,
            "manage_channel_webhook",
            AsyncMock(return_value=True),
        ) as webhook_mock,
    ):
        await handlers.handle_channel_unlink_callback(mock_telegram_update, mock_telegram_context)

    updated_subscriptions = (
        (
            await async_db_session.execute(
                select(Subscription).where(Subscription.chat_id == channel_chat.id)
            )
        )
        .scalars()
        .all()
    )
    assert all(not sub.is_active for sub in updated_subscriptions)

    updated_link = await async_db_session.execute(select(ChannelAdminLink))
    assert updated_link.scalar_one().revoked_at is not None

    refreshed_channel = await async_db_session.get(Chat, channel_chat.id)
    assert refreshed_channel.is_active is False

    refreshed_actor = await async_db_session.get(Chat, actor_chat.id)
    assert refreshed_actor.active_channel_chat_id is None

    query.edit_message_text.assert_called_once()
    call_args = webhook_mock.await_args_list
    assert len(call_args) == 2
    assert {args.args[0] for args in call_args} == {"UCunlink1", "UCunlink2"}


@allure.feature("Bot Handlers")
@allure.story("Channel Context")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_list_command_clears_context_when_admin_revoked(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """DM commands should drop channel context when Telegram revokes admin rights."""
    mock_acl = MagicMock(spec=ACLService)
    mock_acl.verify_admin = AsyncMock(return_value=False)
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot, acl_service=mock_acl)

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    private_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channel_chat = Chat(
        chat_id="-100555666777",
        chat_type="channel",
        title="Linked Channel",
    )
    async_db_session.add_all([private_chat, channel_chat])
    await async_db_session.flush()
    private_chat.active_channel_chat_id = channel_chat.id
    now = datetime.now(UTC).replace(tzinfo=None)
    private_chat.active_channel_selected_at = now
    private_chat.active_channel_expires_at = now + timedelta(minutes=60)
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel_chat.id,
            admin_user_id=db_user.id,
            role="administrator",
        )
    )
    await async_db_session.commit()
    mock_telegram_update.message.reply_text.reset_mock()

    verify_patch = AsyncMock(return_value=(True, []))
    with (
        patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session),
        patch.object(handlers, "_verify_bot_permissions", verify_patch),
    ):
        await handlers.list_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called()
    first_reply = mock_telegram_update.message.reply_text.call_args.args[0]
    assert "revoked" in first_reply.lower()

    refreshed = await async_db_session.get(Chat, private_chat.id)
    assert refreshed.active_channel_chat_id is None

    link_row = await async_db_session.execute(select(ChannelAdminLink))
    assert link_row.scalar_one().revoked_at is not None


@allure.feature("Bot Handlers")
@allure.story("Channel Context")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_forwarded_message_switches_channel_context(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Forwarding a linked channel message in a DM should switch the active context."""
    mock_acl = MagicMock(spec=ACLService)
    mock_acl.verify_admin = AsyncMock(return_value=True)
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot, acl_service=mock_acl)

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="forwarduser",
        first_name="Forward",
        last_name="User",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channel_chat = Chat(
        chat_id="-100333444555",
        chat_type="channel",
        title="Forward Channel",
    )
    async_db_session.add_all([actor_chat, channel_chat])
    await async_db_session.flush()
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel_chat.id,
            admin_user_id=db_user.id,
            role="administrator",
        )
    )
    await async_db_session.commit()
    message = SimpleNamespace(
        reply_text=AsyncMock(),
        chat=mock_telegram_update.effective_chat,
        from_user=mock_telegram_update.effective_user,
        text="",
    )
    forwarded = SimpleNamespace(
        type="channel",
        id=int(channel_chat.chat_id),
        title=channel_chat.title,
    )
    message.forward_origin = SimpleNamespace(chat=forwarded)
    message.external_reply = None
    mock_telegram_update.message = message
    mock_telegram_update.effective_message = message

    verify_patch = AsyncMock(return_value=(True, []))
    with (
        patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session),
        patch.object(handlers, "_verify_bot_permissions", verify_patch),
    ):
        await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    updated_chat = await async_db_session.get(Chat, actor_chat.id)
    assert updated_chat.active_channel_chat_id == channel_chat.id
    mock_telegram_update.message.reply_text.assert_called()
    success_text = mock_telegram_update.message.reply_text.call_args.args[0]
    assert "channel context" in success_text.lower()


@allure.feature("Bot Handlers")
@allure.story("Channel Selection")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_channel_select_command_renders_keyboard(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure /channel_select surfaces linked channels via inline keyboard."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.message.reply_text.reset_mock()

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="selector",
        first_name="Select",
        last_name="User",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channels = [
        Chat(chat_id="-100200300401", chat_type="channel", title="Alpha Channel"),
        Chat(chat_id="-100200300402", chat_type="channel", title="Beta Channel"),
    ]
    async_db_session.add(actor_chat)
    async_db_session.add_all(channels)
    await async_db_session.flush()
    for channel in channels:
        async_db_session.add(
            ChannelAdminLink(
                channel_chat_id=channel.id,
                admin_user_id=db_user.id,
                role="administrator",
            )
        )
    await async_db_session.commit()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.channel_select_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called()
    reply_kwargs = mock_telegram_update.message.reply_text.call_args.kwargs
    markup = reply_kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    # 2 channel buttons + 1 clear button
    assert len(markup.inline_keyboard) == 3
    assert any(
        "chanselect::set" in button.callback_data
        for row in markup.inline_keyboard
        for button in row
    )


@allure.feature("Bot Handlers")
@allure.story("Channel Selection")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_select_callback_switches_channel(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Selecting a channel via callback should set the DM context."""
    mock_acl = MagicMock(spec=ACLService)
    mock_acl.verify_admin = AsyncMock(return_value=True)
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot, acl_service=mock_acl)

    user_repo = UserRepository(async_db_session)
    db_user = await user_repo.get_or_create_user(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="selector",
        first_name="Select",
        last_name="User",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user_id=db_user.id,
    )
    channel = Chat(
        chat_id="-100987650001",
        chat_type="channel",
        title="Callback Channel",
    )
    async_db_session.add_all([actor_chat, channel])
    await async_db_session.flush()
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel.id,
            admin_user_id=db_user.id,
            role="administrator",
        )
    )
    await async_db_session.commit()

    query = MagicMock(spec=CallbackQuery)
    query.data = f"chanselect::set::{channel.id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.message.chat = mock_telegram_update.effective_chat
    mock_telegram_update.callback_query = query
    mock_telegram_update.effective_message = query.message
    mock_telegram_update.effective_chat = mock_telegram_update.effective_chat

    verify_patch = AsyncMock(return_value=(True, []))
    with (
        patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session),
        patch.object(handlers, "_verify_bot_permissions", verify_patch),
    ):
        await handlers.handle_channel_select_callback(mock_telegram_update, mock_telegram_context)

    updated_chat = await async_db_session.get(Chat, actor_chat.id)
    assert updated_chat.active_channel_chat_id == channel.id
    query.edit_message_text.assert_called()


@allure.feature("Bot Handlers")
@allure.story("Webhook Management")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_clears_channel_webhook(
    mock_youtube_api,
    mock_telegram_update,
    mock_telegram_context,
    async_db_session,
):
    """Ensure webhook metadata resets when the last subscriber leaves."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)
    handlers.check_if_channel_has_other_subscribers = AsyncMock(return_value=False)

    chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title=mock_telegram_update.effective_chat.username,
    )
    channel = YouTubeChannel(
        channel_id="UClegacy",
        channel_name="Legacy Channel",
        channel_url="https://youtube.com/channel/UClegacy",
    )
    async_db_session.add_all([chat, channel])
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()
    subscription.webhook_url = "https://old.example/webhook"
    await async_db_session.commit()

    query = MagicMock()
    query.data = f"unsub_{channel.id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    mock_telegram_update.callback_query = query

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.handle_unsubscribe_callback(mock_telegram_update, mock_telegram_context)

    updated_subscription = await async_db_session.get(Subscription, subscription.id)
    assert updated_subscription.webhook_url is None


@allure.feature("Bot Handlers")
@allure.story("Subscription Checks")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_check_if_channel_has_other_subscribers_true(
    mock_youtube_api, async_db_session, mock_telegram_bot
):
    """Test checking for other subscribers returns True when others exist.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
        mock_telegram_bot: Mock Telegram bot fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_bot)

    # Create channel with multiple subscribers
    user1 = User(telegram_id="111", username="user1", first_name="User", last_name="One")
    user2 = User(telegram_id="222", username="user2", first_name="User", last_name="Two")
    chat1 = Chat(chat_id="111", chat_type="private", title="user1")
    chat2 = Chat(chat_id="222", chat_type="private", title="user2")
    async_db_session.add_all([user1, user2, chat1, chat2])
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    sub1 = Subscription(chat_id=chat1.id, channel_id=channel.id, is_active=True)
    sub2 = Subscription(chat_id=chat2.id, channel_id=channel.id, is_active=True)
    async_db_session.add_all([sub1, sub2])
    await async_db_session.commit()

    # Check if channel has other subscribers excluding user1
    result = await handlers.check_if_channel_has_other_subscribers(
        async_db_session, channel.id, exclude_chat_id=chat1.id
    )

    assert result is True


@allure.feature("Bot Handlers")
@allure.story("Subscription Checks")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_check_if_channel_has_other_subscribers_false(
    mock_youtube_api, async_db_session, mock_telegram_bot
):
    """Test checking for other subscribers returns False when only one exists.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
        mock_telegram_bot: Mock Telegram bot fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_bot)

    # Create channel with single subscriber
    user = User(telegram_id="111", username="user1", first_name="User", last_name="One")
    chat = Chat(chat_id="111", chat_type="private", title="user1")
    async_db_session.add_all([user, chat])
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()

    # Check if channel has other subscribers excluding the only user
    result = await handlers.check_if_channel_has_other_subscribers(
        async_db_session, channel.id, exclude_chat_id=chat.id
    )

    assert result is False


@allure.feature("Bot Handlers")
@allure.story("Language Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_language_command_renders_keyboard(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Language command should present localized prompt with keyboard."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.effective_user.language_code = "en"

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.language_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.assert_called_once()
    args, kwargs = mock_telegram_update.message.reply_text.call_args
    assert "Select your preferred language" in args[0]
    markup = kwargs["reply_markup"]
    assert isinstance(markup, InlineKeyboardMarkup)
    assert markup.inline_keyboard[0][0].callback_data == "lang::en"


@allure.feature("Bot Handlers")
@allure.story("Language Command")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_language_callback_updates_chat_locale(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Callback should persist the chosen locale."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    mock_telegram_update.effective_user.language_code = "en"

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.language_command(mock_telegram_update, mock_telegram_context)

    mock_telegram_update.message.reply_text.reset_mock()
    query = MagicMock()
    query.data = "lang::ru"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.message.chat = mock_telegram_update.effective_chat
    mock_telegram_update.callback_query = query

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.handle_language_callback(mock_telegram_update, mock_telegram_context)

    chat_row = await async_db_session.execute(select(Chat))
    chat = chat_row.scalar_one()
    assert chat.preferred_locale == "ru"
    query.edit_message_text.assert_awaited()
