"""Unit tests for bot command handlers.

Tests cover all command handlers including /start, /help, /subscribe, /list,
/unsubscribe, callback query handling, and YouTube URL processing.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from telegram import CallbackQuery, InlineKeyboardMarkup

from src.bot.handlers import BotHandlers
from src.database.models import Subscription, User, YouTubeChannel
from src.database.repository import UserRepository


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
    handlers = BotHandlers(mock_youtube_api)

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
async def test_help_command(mock_telegram_update, mock_telegram_context, mock_youtube_api):
    """Test /help command returns help text.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
    """
    handlers = BotHandlers(mock_youtube_api)

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
    handlers = BotHandlers(mock_youtube_api)
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
    handlers = BotHandlers(mock_youtube_api)
    mock_telegram_context.args = ["https://youtube.com/@testchannel"]

    # Mock handle_youtube_url to verify it was called
    handlers.handle_youtube_url = AsyncMock()

    await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify handle_youtube_url was called with the URL
    handlers.handle_youtube_url.assert_called_once_with(
        mock_telegram_update, mock_telegram_context, "https://youtube.com/@testchannel"
    )


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
    handlers = BotHandlers(mock_youtube_api)

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
    handlers = BotHandlers(mock_youtube_api)

    # Create user, channel, and subscription
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(user_id=user.id, channel_id=channel.id, is_active=True)
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
    handlers = BotHandlers(mock_youtube_api)

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
    handlers = BotHandlers(mock_youtube_api)

    # Create user, channel, and subscription
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(user_id=user.id, channel_id=channel.id, is_active=True)
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
    handlers = BotHandlers(mock_youtube_api)

    # Setup callback query
    query = MagicMock(spec=CallbackQuery)
    query.data = "cancel"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    mock_telegram_update.callback_query = query

    await handlers.handle_unsubscribe_callback(mock_telegram_update, mock_telegram_context)

    # Verify callback was answered and message edited
    query.answer.assert_called_once()
    query.edit_message_text.assert_called_once_with("Cancelled.")


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
    handlers = BotHandlers(mock_youtube_api)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)
    handlers.check_if_channel_has_other_subscribers = AsyncMock(return_value=False)

    # Create user, channel, and subscription
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(user_id=user.id, channel_id=channel.id, is_active=True)
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
    handlers = BotHandlers(mock_youtube_api)
    handlers.handle_youtube_url = AsyncMock()

    mock_telegram_update.message.text = "Check this out: https://youtube.com/@testchannel"

    await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    # Verify handle_youtube_url was called
    handlers.handle_youtube_url.assert_called_once()
    call_args = handlers.handle_youtube_url.call_args[0]
    assert "youtube.com" in call_args[2]


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
    handlers = BotHandlers(mock_youtube_api)

    mock_telegram_update.message.text = "Hello bot, how are you?"

    await handlers.handle_message(mock_telegram_update, mock_telegram_context)

    # Verify help message was sent
    mock_telegram_update.message.reply_text.assert_called_once()
    call_args = mock_telegram_update.message.reply_text.call_args[0][0]
    assert "Send me a YouTube URL" in call_args


@allure.feature("Bot Handlers")
@allure.story("Webhook Management")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_manage_channel_webhook_subscribe(mock_youtube_api, mock_pubsub_manager):
    """Test webhook management for subscribing to a channel.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        mock_pubsub_manager: Mock PubSubManager fixture.
    """
    handlers = BotHandlers(mock_youtube_api)
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
async def test_manage_channel_webhook_unsubscribe(mock_youtube_api, mock_pubsub_manager):
    """Test webhook management for unsubscribing from a channel.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        mock_pubsub_manager: Mock PubSubManager fixture.
    """
    handlers = BotHandlers(mock_youtube_api)
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
async def test_manage_channel_webhook_error_handling(mock_youtube_api, mock_pubsub_manager):
    """Test webhook management handles errors gracefully.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        mock_pubsub_manager: Mock PubSubManager fixture.
    """
    handlers = BotHandlers(mock_youtube_api)
    handlers.webhook_manager = mock_pubsub_manager
    mock_pubsub_manager.subscribe_to_channel = AsyncMock(side_effect=Exception("Network error"))

    result = await handlers.manage_channel_webhook("UCtest123", "subscribe")

    # Verify error was handled
    assert result is False


@allure.feature("Bot Handlers")
@allure.story("Subscription Checks")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_check_if_channel_has_other_subscribers_true(mock_youtube_api, async_db_session):
    """Test checking for other subscribers returns True when others exist.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api)

    # Create channel with multiple subscribers
    user1 = User(telegram_id="111", username="user1", first_name="User", last_name="One")
    user2 = User(telegram_id="222", username="user2", first_name="User", last_name="Two")
    async_db_session.add_all([user1, user2])
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    sub1 = Subscription(user_id=user1.id, channel_id=channel.id, is_active=True)
    sub2 = Subscription(user_id=user2.id, channel_id=channel.id, is_active=True)
    async_db_session.add_all([sub1, sub2])
    await async_db_session.commit()

    # Check if channel has other subscribers excluding user1
    result = await handlers.check_if_channel_has_other_subscribers(
        async_db_session, channel.id, exclude_user_id=user1.id
    )

    assert result is True


@allure.feature("Bot Handlers")
@allure.story("Subscription Checks")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_check_if_channel_has_other_subscribers_false(mock_youtube_api, async_db_session):
    """Test checking for other subscribers returns False when only one exists.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api)

    # Create channel with single subscriber
    user = User(telegram_id="111", username="user1", first_name="User", last_name="One")
    async_db_session.add(user)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    subscription = Subscription(user_id=user.id, channel_id=channel.id, is_active=True)
    async_db_session.add(subscription)
    await async_db_session.commit()

    # Check if channel has other subscribers excluding the only user
    result = await handlers.check_if_channel_has_other_subscribers(
        async_db_session, channel.id, exclude_user_id=user.id
    )

    assert result is False
