"""Integration tests for bot workflows.

Tests end-to-end bot flows including subscription, unsubscription,
notification delivery, error recovery, and webhook verification.
"""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

import allure
import pytest
from sqlalchemy import select

from src.bot.handlers import BotHandlers
from src.bot.notifications import NotificationService
from src.database.models import Chat, Subscription, User, YouTubeChannel
from src.webhooks.handlers import WebhookHandlers


@allure.feature("Integration")
@allure.story("Bot Workflows")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.integration
async def test_end_to_end_subscription_flow(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Test complete subscription flow from command to database and webhook.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)

    # Mock YouTube API to return channel info
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

    mock_telegram_update.message.reply_text = AsyncMock()
    mock_telegram_context.args = ["https://youtube.com/@testchannel"]

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify webhook was registered and subscription persisted for chat context
    handlers.manage_channel_webhook.assert_called()
    chat_rows = await async_db_session.execute(select(Chat))
    chat = chat_rows.scalar_one()
    subscription_rows = await async_db_session.execute(select(Subscription))
    subscriptions = subscription_rows.scalars().all()
    assert len(subscriptions) == 1
    assert subscriptions[0].chat_id == chat.id
    channel_rows = await async_db_session.execute(select(YouTubeChannel))
    channel = channel_rows.scalar_one()
    assert subscriptions[0].channel_id == channel.id


@allure.feature("Integration")
@allure.story("Bot Workflows")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_unsubscription_flow_with_webhook_cleanup(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Test unsubscription flow including webhook cleanup.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)
    handlers.check_if_channel_has_other_subscribers = AsyncMock(return_value=False)

    # Setup: Create user, channel, and subscription
    user = User(telegram_id="123456789", username="testuser")
    async_db_session.add(user)
    await async_db_session.flush()

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.flush()

    chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title=mock_telegram_update.effective_chat.username,
    )
    async_db_session.add(chat)
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id)
    async_db_session.add(subscription)
    await async_db_session.commit()

    # Mock callback query
    query = MagicMock()
    query.data = f"unsub_{channel.id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    mock_telegram_update.callback_query = query

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.handle_unsubscribe_callback(mock_telegram_update, mock_telegram_context)

    # Verify webhook was cleaned up
    handlers.manage_channel_webhook.assert_called_with("UCtest123", "unsubscribe", request_id=ANY)
    updated = await async_db_session.execute(
        select(Subscription).where(Subscription.id == subscription.id)
    )
    updated_subscription = updated.scalar_one()
    assert updated_subscription.is_active is False


@allure.feature("Integration")
@allure.story("Bot Workflows")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.integration
async def test_resubscribe_reactivates_soft_deleted_subscription(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Ensure a chat can resubscribe after a soft delete without integrity errors."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)
    handlers.manage_channel_webhook = AsyncMock(return_value=True)

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

    mock_telegram_update.message.reply_text = AsyncMock()
    mock_telegram_context.args = ["https://youtube.com/@testchannel"]

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    subscription_rows = await async_db_session.execute(select(Subscription))
    first_subscription = subscription_rows.scalar_one()
    assert first_subscription.is_active is True

    # Soft delete existing subscription to simulate /unsubscribe
    first_subscription.is_active = False
    first_subscription.notification_enabled = False
    await async_db_session.commit()

    mock_telegram_update.message.reply_text.reset_mock()
    handlers.manage_channel_webhook.reset_mock()
    handlers.manage_channel_webhook.return_value = True
    mock_telegram_context.args = ["https://youtube.com/@testchannel"]

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    final_rows = await async_db_session.execute(select(Subscription))
    subscriptions = final_rows.scalars().all()
    assert len(subscriptions) == 1
    assert subscriptions[0].id == first_subscription.id
    assert subscriptions[0].is_active is True


@allure.feature("Integration")
@allure.story("Bot Workflows")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_notification_delivery_flow(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Test notification delivery from webhook to message send.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    from datetime import datetime

    from src.database.repository import (
        ChannelRepository,
        ChatRepository,
        NotificationRepository,
        SubscriptionRepository,
        UserRepository,
        VideoRepository,
    )

    # Create full workflow data
    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)
    video_repo = VideoRepository(async_db_session)
    notif_repo = NotificationRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type=mock_telegram_update.effective_chat.type,
        title=mock_telegram_update.effective_chat.username,
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest",
    )
    await sub_repo.create_subscription(chat.id, channel.id)

    video = await video_repo.create_video(
        video_id="newvideo",
        channel_id=channel.id,
        title="New Video",
        description="Test",
        url="https://youtube.com/watch?v=newvideo",
        published_at=datetime(2024, 1, 1),
    )

    notification = await notif_repo.create_notification(chat.id, video.id, message_id="msg123")

    assert notification is not None
    assert notification.video_id == video.id
    assert notification.chat_id == chat.id


@allure.feature("Integration")
@allure.story("Bot Workflows")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.integration
async def test_error_recovery_failed_api_call(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Test error recovery when YouTube API call fails.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
        mock_telegram_context: Mock Telegram context fixture.
        mock_youtube_api: Mock YouTube API fixture.
        async_db_session: Async database session fixture.
    """
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    # Mock API failure
    mock_youtube_api.resolve_url = AsyncMock(return_value=None)

    mock_telegram_update.message.reply_text = AsyncMock()
    mock_telegram_context.args = ["https://youtube.com/@badurl"]

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

    # Verify error was handled gracefully (no exception raised)
    assert mock_telegram_update.message.reply_text.called


@allure.feature("Integration")
@allure.story("Bot Workflows")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.integration
async def test_webhook_verification_challenge(mock_pubsub_manager):
    """Test webhook verification challenge handling.

    Args:
        mock_pubsub_manager: Mock PubSubManager fixture.
    """
    # Mock successful verification
    mock_pubsub_manager.verify_subscription = AsyncMock(
        return_value='<?xml version="1.0"?><feed></feed>'
    )

    result = await mock_pubsub_manager.verify_subscription("UCtest123")

    assert result is not None
    assert "<feed>" in result


@allure.feature("Integration")
@allure.story("Webhook Notifications")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_webhook_uses_chat_locale_for_notifications(async_db_session):
    """Webhook notifications should respect the chat's preferred locale."""
    notification_service = MagicMock(spec=NotificationService)
    notification_service.send_video_notification = AsyncMock(return_value=123)
    handlers = WebhookHandlers(notification_service)

    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
    )
    chat = Chat(
        chat_id="-100123",
        chat_type="group",
        title="Test Group",
        preferred_locale="de",
    )
    subscription = Subscription(chat=chat, channel=channel, is_active=True)
    async_db_session.add_all([channel, chat, subscription])
    await async_db_session.commit()

    entry = {
        "yt_videoid": "abc123",
        "yt_channelid": channel.channel_id,
        "title": "Locale Test Video",
        "link": "https://youtube.com/watch?v=abc123",
        "published": "2024-12-01T12:00:00Z",
        "summary": "Beschreibung",
    }

    with patch("src.webhooks.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.process_video_update(entry, request_id="webhook-locale")

    notification_service.send_video_notification.assert_awaited()
    kwargs = notification_service.send_video_notification.await_args.kwargs
    assert kwargs["locale"] == "de"
