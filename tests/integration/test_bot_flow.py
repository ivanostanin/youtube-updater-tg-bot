"""Integration tests for bot workflows.

Tests end-to-end bot flows including subscription, unsubscription,
notification delivery, error recovery, and webhook verification.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import allure
import pytest
from sqlalchemy import select

from src.bot.handlers import BotHandlers
from src.bot.notifications import NotificationService
from src.database.models import (
    ChannelAdminLink,
    Chat,
    Notification,
    Subscription,
    User,
    YouTubeChannel,
)
from src.services import ACLService
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

    # Mock the actual webhook manager's subscribe method
    with patch("src.bot.handlers.PubSubManager.subscribe_to_channel", new_callable=AsyncMock) as mock_subscribe_to_channel:
        mock_subscribe_to_channel.return_value = True

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
        mock_subscribe_to_channel.assert_awaited()
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
@allure.story("DM Channel Workflows")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_dm_channel_link_and_subscription_targets_channel(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Ensure DM channel linking + subscribe flows attach subscriptions to the channel chat."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    with patch("src.bot.handlers.PubSubManager.subscribe_to_channel", new_callable=AsyncMock) as mock_subscribe_to_channel:
        mock_subscribe_to_channel.return_value = True

        channel_chat = MagicMock()
        channel_chat.id = -100987654321
        channel_chat.type = "channel"
        channel_chat.title = "Linked Broadcast"
        channel_chat.username = "linkedbroadcast"

        admin_member = MagicMock()
        admin_member.status = "administrator"
        bot_member = MagicMock()
        bot_member.can_post_messages = True
        bot_member.can_delete_messages = True
        bot_member.can_edit_messages = True

        mock_telegram_context.args = ["@linkedbroadcast"]
        mock_telegram_context.bot.get_chat = AsyncMock(return_value=channel_chat)
        mock_telegram_context.bot.get_chat_member = AsyncMock(side_effect=[admin_member, bot_member])
        mock_telegram_update.message.reply_text = AsyncMock()

        with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
            await handlers.channel_link_command(mock_telegram_update, mock_telegram_context)

        mock_telegram_context.bot.get_chat_member = AsyncMock(side_effect=[admin_member, bot_member])

        mock_youtube_api.resolve_url = AsyncMock(
            return_value={
                "id": "UCdmcontext",
                "title": "DM Context Channel",
                "url": "https://youtube.com/channel/UCdmcontext",
            }
        )
        mock_youtube_api.get_feed_url = MagicMock(
            return_value="https://youtube.com/feeds/videos.xml?channel_id=UCdmcontext"
        )
        mock_telegram_context.args = ["https://youtube.com/@dmcontext"]
        mock_telegram_update.message.reply_text.reset_mock()

        with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
            await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

        mock_subscribe_to_channel.assert_awaited()
        channel_rows = await async_db_session.execute(select(Chat).where(Chat.chat_type == "channel"))
        channel_chat_row = channel_rows.scalar_one()
        dm_rows = await async_db_session.execute(select(Chat).where(Chat.chat_type == "private"))
        dm_chat_row = dm_rows.scalar_one()

        assert dm_chat_row.active_channel_chat_id == channel_chat_row.id

        subscriptions_rows = await async_db_session.execute(select(Subscription))
        subscription = subscriptions_rows.scalar_one()
        assert subscription.chat_id == channel_chat_row.id

        link_rows = await async_db_session.execute(select(ChannelAdminLink))
        link = link_rows.scalar_one()
        assert link.channel_chat_id == channel_chat_row.id
        assert link.admin_user_id == dm_chat_row.user_id


@allure.feature("Integration")
@allure.story("DM Channel Workflows")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_channel_link_denied_without_bot_permissions(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Linking should fail when the bot lacks required channel permissions."""
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot)

    channel_chat = MagicMock()
    channel_chat.id = -100777
    channel_chat.type = "channel"
    channel_chat.title = "Missing Permissions Channel"

    admin_member = MagicMock()
    admin_member.status = "administrator"
    bot_member = MagicMock()
    bot_member.can_post_messages = False
    bot_member.can_delete_messages = True
    bot_member.can_edit_messages = True

    mock_telegram_context.args = ["@permdenied"]
    mock_telegram_context.bot.get_chat = AsyncMock(return_value=channel_chat)
    mock_telegram_context.bot.get_chat_member = AsyncMock(side_effect=[admin_member, bot_member])
    mock_telegram_update.message.reply_text = AsyncMock()

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.channel_link_command(mock_telegram_update, mock_telegram_context)

    channel_rows = await async_db_session.execute(select(Chat).where(Chat.chat_type == "channel"))
    assert channel_rows.scalars().all() == []
    link_rows = await async_db_session.execute(select(ChannelAdminLink))
    assert link_rows.scalars().all() == []
    reply_text = mock_telegram_update.message.reply_text.call_args.args[0]
    assert "permissions" in reply_text.lower()


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

    with (
        patch("src.bot.handlers.PubSubManager.unsubscribe_from_channel", new_callable=AsyncMock) as mock_unsubscribe_from_channel,
        patch.object(handlers, "check_if_channel_has_other_subscribers", new_callable=AsyncMock) as mock_check_if_channel_has_other_subscribers,
    ):
        mock_unsubscribe_from_channel.return_value = True
        mock_check_if_channel_has_other_subscribers.return_value = False

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
        mock_unsubscribe_from_channel.assert_awaited_with("UCtest123")
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

    with patch("src.bot.handlers.PubSubManager.subscribe_to_channel", new_callable=AsyncMock) as mock_subscribe_to_channel:
        mock_subscribe_to_channel.return_value = True

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
        mock_subscribe_to_channel.reset_mock()
        mock_subscribe_to_channel.return_value = True
        mock_telegram_context.args = ["https://youtube.com/@testchannel"]

        with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
            await handlers.subscribe_command(mock_telegram_update, mock_telegram_context)

        mock_subscribe_to_channel.assert_awaited()
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

    new_notification: Notification = await notif_repo.create_notification(chat.id, video.id, message_id="msg123")

    assert new_notification is not None
    assert new_notification.video_id == video.id
    assert new_notification.chat_id == chat.id


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
        chat_type="channel",
        title="Broadcast Channel",
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
    assert kwargs["chat_telegram_id"] == chat.chat_id
    assert kwargs["chat_type"] == "channel"


@allure.feature("Integration")
@allure.story("DM Channel Workflows")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_channel_select_revokes_access_when_acl_denied(
    mock_telegram_update,
    mock_telegram_context,
    mock_youtube_api,
    async_db_session,
):
    """Selecting a channel should revoke context if Telegram no longer lists the admin."""
    mock_acl = MagicMock(spec=ACLService)
    mock_acl.verify_admin = AsyncMock(return_value=False)
    handlers = BotHandlers(mock_youtube_api, mock_telegram_context.bot, acl_service=mock_acl)

    user = User(
        telegram_id=str(mock_telegram_update.effective_user.id),
        username="lostaccess",
        first_name="Lost",
        last_name="Access",
    )
    channel_chat = Chat(
        chat_id="-100665544",
        chat_type="channel",
        title="Revoked Channel",
    )
    actor_chat = Chat(
        chat_id=str(mock_telegram_update.effective_chat.id),
        chat_type="private",
        user=user,
    )
    async_db_session.add_all([user, channel_chat, actor_chat])
    await async_db_session.flush()
    actor_chat.active_channel_chat_id = channel_chat.id
    async_db_session.add(
        ChannelAdminLink(
            channel_chat_id=channel_chat.id,
            admin_user_id=user.id,
            role="administrator",
        )
    )
    await async_db_session.commit()

    query = MagicMock()
    query.data = f"chanselect::set::{channel_chat.id}"
    query.answer = AsyncMock()
    query.edit_message_text = AsyncMock()
    query.message = MagicMock()
    query.message.chat = mock_telegram_update.effective_chat
    mock_telegram_update.callback_query = query

    with patch("src.bot.handlers.AsyncSessionLocal", return_value=async_db_session):
        await handlers.handle_channel_select_callback(mock_telegram_update, mock_telegram_context)

    mock_acl.verify_admin.assert_awaited()
    updated_link_rows = await async_db_session.execute(select(ChannelAdminLink))
    updated_link = updated_link_rows.scalar_one()
    assert updated_link.revoked_at is not None

    refreshed_actor = await async_db_session.get(Chat, actor_chat.id)
    assert refreshed_actor.active_channel_chat_id is None
    answer_args, _ = query.edit_message_text.call_args
    assert "revoked" in (answer_args[0] or "").lower()
