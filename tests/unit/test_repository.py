"""Unit tests for database models and repositories.

Tests cover all repository operations including user, channel, subscription,
video, and notification management, along with model relationships.
"""

from datetime import UTC, datetime, timedelta

import allure
import pytest
from sqlalchemy import select

from src.database.models import Chat, Subscription, User, YouTubeChannel
from src.database.repository import (
    ChannelRepository,
    ChatRepository,
    NotificationRepository,
    SubscriptionRepository,
    UserRepository,
    VideoRepository,
)


@allure.feature("Database")
@allure.story("Models")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_user_model_creation(async_db_session) -> None:
    """Test User model creation and basic attributes.

    Args:
        async_db_session: Async database session fixture.
    """
    user = User(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.commit()

    assert user.id is not None
    assert user.telegram_id == "123456789"
    assert user.username == "testuser"
    assert user.is_active is True


@allure.feature("Database")
@allure.story("Models")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_youtube_channel_model_creation(async_db_session) -> None:
    """Test YouTubeChannel model creation and attributes.

    Args:
        async_db_session: Async database session fixture.
    """
    channel = YouTubeChannel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )
    async_db_session.add(channel)
    await async_db_session.commit()

    assert channel.id is not None
    assert channel.channel_id == "UCtest123"
    assert channel.is_active is True


@allure.feature("Database")
@allure.story("Models")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_model_with_relationships(async_db_session) -> None:
    """Test Subscription model with user and channel relationships.

    Args:
        async_db_session: Async database session fixture.
    """
    user = User(telegram_id="123", username="test", first_name="Test")
    channel = YouTubeChannel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )
    chat = Chat(chat_id="123", chat_type="private", title="Test Chat")
    async_db_session.add_all([user, channel, chat])
    await async_db_session.flush()

    subscription = Subscription(chat_id=chat.id, channel_id=channel.id)
    async_db_session.add(subscription)
    await async_db_session.commit()

    # Verify relationships
    result = await async_db_session.execute(
        select(Subscription).where(Subscription.id == subscription.id)
    )
    saved_sub = result.scalar_one()

    assert saved_sub.chat_id == chat.id
    assert saved_sub.channel_id == channel.id
    assert saved_sub.is_active is True


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_user_repository_create_new_user(async_db_session) -> None:
    """Test UserRepository creates new user when doesn't exist.

    Args:
        async_db_session: Async database session fixture.
    """
    repo = UserRepository(async_db_session)

    user = await repo.get_or_create_user(
        telegram_id="123456789",
        username="newuser",
        first_name="New",
        last_name="User",
    )

    assert user.id is not None
    assert user.telegram_id == "123456789"
    assert user.username == "newuser"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_user_repository_get_existing_user(async_db_session) -> None:
    """Test UserRepository returns existing user without creating duplicate.

    Args:
        async_db_session: Async database session fixture.
    """
    repo = UserRepository(async_db_session)

    # Create user first time
    user1 = await repo.get_or_create_user(
        telegram_id="123456789",
        username="existinguser",
    )

    # Get same user
    user2 = await repo.get_or_create_user(telegram_id="123456789")

    assert user1.id == user2.id
    assert user1.telegram_id == user2.telegram_id


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_user_repository_get_by_telegram_id(async_db_session) -> None:
    """Test UserRepository retrieves user by Telegram ID.

    Args:
        async_db_session: Async database session fixture.
    """
    repo = UserRepository(async_db_session)

    await repo.get_or_create_user(telegram_id="123456789", username="findme")

    user = await repo.get_user_by_telegram_id("123456789")

    assert user is not None
    assert user.telegram_id == "123456789"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_chat_repository_tracks_user_relationship(async_db_session) -> None:
    """Ensure ChatRepository persists and updates user references for chats."""
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)

    user = await user_repo.get_or_create_user(telegram_id="321", username="chat-owner")

    chat = await chat_repo.get_or_create_chat(
        chat_id="321",
        chat_type="private",
        title="Owner Chat",
        user_id=user.id,
    )

    assert chat.user_id == user.id

    # Updates should overwrite the relationship when a new user is provided
    new_user = await user_repo.get_or_create_user(telegram_id="654", username="new-owner")
    updated = await chat_repo.get_or_create_chat(
        chat_id="321",
        chat_type="private",
        title="Owner Chat",
        user_id=new_user.id,
    )

    assert updated.user_id == new_user.id


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_channel_repository_create_new_channel(async_db_session) -> None:
    """Test ChannelRepository creates new channel when doesn't exist.

    Args:
        async_db_session: Async database session fixture.
    """
    repo = ChannelRepository(async_db_session)

    channel = await repo.get_or_create_channel(
        channel_id="UCnew123",
        channel_name="New Channel",
        channel_url="https://youtube.com/channel/UCnew123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCnew123",
    )

    assert channel.id is not None
    assert channel.channel_id == "UCnew123"
    assert channel.channel_name == "New Channel"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_repository_get_existing_channel(async_db_session) -> None:
    """Test ChannelRepository returns existing channel without duplicate.

    Args:
        async_db_session: Async database session fixture.
    """
    repo = ChannelRepository(async_db_session)

    # Create channel first time
    channel1 = await repo.get_or_create_channel(
        channel_id="UCexist123",
        channel_name="Existing Channel",
        channel_url="https://youtube.com/channel/UCexist123",
    )

    # Get same channel
    channel2 = await repo.get_or_create_channel(
        channel_id="UCexist123",
        channel_name="Existing Channel",
        channel_url="https://youtube.com/channel/UCexist123",
    )

    assert channel1.id == channel2.id


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_repository_get_all_active_channels(async_db_session) -> None:
    """Test ChannelRepository retrieves all active channels.

    Args:
        async_db_session: Async database session fixture.
    """
    repo = ChannelRepository(async_db_session)

    # Create active channel
    await repo.get_or_create_channel(
        channel_id="UCactive1",
        channel_name="Active 1",
        channel_url="https://youtube.com/channel/UCactive1",
    )

    # Create inactive channel
    channel2 = YouTubeChannel(
        channel_id="UCinactive",
        channel_name="Inactive",
        channel_url="https://youtube.com/channel/UCinactive",
        is_active=False,
    )
    async_db_session.add(channel2)
    await async_db_session.commit()

    channels = await repo.get_all_active_channels()

    assert len(channels) == 1
    assert channels[0].channel_id == "UCactive1"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_subscription_repository_create_subscription(async_db_session) -> None:
    """Test SubscriptionRepository creates new subscription.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id="123",
        chat_type="private",
        title="Test User",
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    subscription = await sub_repo.create_subscription(chat.id, channel.id)

    assert subscription.id is not None
    assert subscription.chat_id == chat.id
    assert subscription.channel_id == channel.id
    assert subscription.is_active is True


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_create_subscription_deduplicates(async_db_session) -> None:
    """Ensure create_subscription cleans up stray duplicates before reactivation."""

    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    chat = await chat_repo.get_or_create_chat(
        chat_id="dup-create", chat_type="private", title="Test"
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCdupcreate",
        channel_name="Dup Create",
        channel_url="https://youtube.com/channel/UCdupcreate",
    )

    original = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=False)
    duplicate = Subscription(chat_id=chat.id, channel_id=channel.id, is_active=True)
    async_db_session.add_all([original, duplicate])
    await async_db_session.commit()

    subscription = await sub_repo.create_subscription(chat.id, channel.id)

    assert subscription.is_active is True
    result = await async_db_session.execute(
        select(Subscription)
        .where(Subscription.chat_id == chat.id)
        .where(Subscription.channel_id == channel.id)
    )
    rows = result.scalars().all()
    assert len(rows) == 1


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_get_user_subscriptions(async_db_session) -> None:
    """Test SubscriptionRepository retrieves user's subscriptions.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id="123",
        chat_type="private",
        title="Test User",
    )
    channel1 = await channel_repo.get_or_create_channel(
        channel_id="UC1", channel_name="Channel 1", channel_url="https://youtube.com/channel/UC1"
    )
    channel2 = await channel_repo.get_or_create_channel(
        channel_id="UC2", channel_name="Channel 2", channel_url="https://youtube.com/channel/UC2"
    )

    await sub_repo.create_subscription(chat.id, channel1.id)
    await sub_repo.create_subscription(chat.id, channel2.id)

    subscriptions = await sub_repo.get_chat_subscriptions(chat.id)

    assert len(subscriptions) == 2
    channel_ids = {sub.channel.channel_id for sub in subscriptions}
    assert "UC1" in channel_ids
    assert "UC2" in channel_ids


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_get_subscription(async_db_session) -> None:
    """Test SubscriptionRepository retrieves specific subscription.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id="123",
        chat_type="private",
        title="Test User",
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    await sub_repo.create_subscription(chat.id, channel.id)

    subscription = await sub_repo.get_subscription(chat.id, channel.id)

    assert subscription is not None
    assert subscription.chat_id == chat.id
    assert subscription.channel_id == channel.id


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_delete_subscription(async_db_session) -> None:
    """Test SubscriptionRepository soft deletes subscription.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id="123",
        chat_type="private",
        title="Test User",
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    await sub_repo.create_subscription(chat.id, channel.id)

    # Delete subscription
    success = await sub_repo.delete_subscription(chat.id, channel.id)
    assert success is True

    # Verify it's no longer active
    subscription = await sub_repo.get_subscription(chat.id, channel.id)
    assert subscription is None  # get_subscription only returns active subscriptions


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_handles_duplicate_rows_on_delete(async_db_session) -> None:
    """Ensure duplicate subscription rows don't break delete flows and are fully deactivated."""

    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    chat = await chat_repo.get_or_create_chat(chat_id="dup-chat", chat_type="private", title="Dup")
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCdup",
        channel_name="Duplicate Channel",
        channel_url="https://youtube.com/channel/UCdup",
    )

    await sub_repo.create_subscription(chat.id, channel.id)

    duplicate = Subscription(chat_id=chat.id, channel_id=channel.id)
    async_db_session.add(duplicate)
    await async_db_session.commit()

    success = await sub_repo.delete_subscription(chat.id, channel.id)
    assert success is True

    result = await async_db_session.execute(
        select(Subscription)
        .where(Subscription.chat_id == chat.id)
        .where(Subscription.channel_id == channel.id)
    )
    records = result.scalars().all()
    assert len(records) == 1
    assert records[0].is_active is False


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_reactivate_subscription(async_db_session) -> None:
    """Test SubscriptionRepository reactivates existing subscriptions."""

    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    chat = await chat_repo.get_or_create_chat(
        chat_id="chat-1", chat_type="private", title="Test Chat"
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCreactivate",
        channel_name="Reactivate Channel",
        channel_url="https://youtube.com/channel/UCreactivate",
    )

    first = await sub_repo.create_subscription(chat.id, channel.id)
    first_id = first.id

    # Soft delete the subscription
    deleted = await sub_repo.delete_subscription(chat.id, channel.id)
    assert deleted is True

    # Recreate should reactivate existing record
    second = await sub_repo.create_subscription(chat.id, channel.id)
    assert second.id == first_id
    assert second.is_active is True
    assert second.notification_enabled is True


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscription_repository_get_channel_subscribers(async_db_session) -> None:
    """Test SubscriptionRepository retrieves channel subscribers.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="111", username="user1")
    await user_repo.get_or_create_user(telegram_id="222", username="user2")
    chat1 = await chat_repo.get_or_create_chat(chat_id="111", chat_type="private", title="user1")
    chat2 = await chat_repo.get_or_create_chat(chat_id="222", chat_type="private", title="user2")
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    await sub_repo.create_subscription(chat1.id, channel.id)
    await sub_repo.create_subscription(chat2.id, channel.id)

    subscribers = await sub_repo.get_channel_subscribers(channel.id)

    assert len(subscribers) == 2
    chat_ids = {sub.chat.chat_id for sub in subscribers}
    assert "111" in chat_ids
    assert "222" in chat_ids


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_video_repository_create_video(async_db_session) -> None:
    """Test VideoRepository creates new video.

    Args:
        async_db_session: Async database session fixture.
    """
    channel_repo = ChannelRepository(async_db_session)
    video_repo = VideoRepository(async_db_session)

    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    video = await video_repo.create_video(
        video_id="dQw4w9WgXcQ",
        channel_id=channel.id,
        title="Test Video",
        description="Test description",
        url="https://youtube.com/watch?v=dQw4w9WgXcQ",
        published_at=datetime(2024, 1, 1, 12, 0, 0),
        thumbnail_url="https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
    )

    assert video.id is not None
    assert video.video_id == "dQw4w9WgXcQ"
    assert video.title == "Test Video"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_video_repository_get_video_by_id(async_db_session) -> None:
    """Test VideoRepository retrieves video by YouTube video ID.

    Args:
        async_db_session: Async database session fixture.
    """
    channel_repo = ChannelRepository(async_db_session)
    video_repo = VideoRepository(async_db_session)

    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    await video_repo.create_video(
        video_id="test123",
        channel_id=channel.id,
        title="Test",
        description="Test",
        url="https://youtube.com/watch?v=test123",
        published_at=datetime(2024, 1, 1),
    )

    video = await video_repo.get_video_by_id("test123")

    assert video is not None
    assert video.video_id == "test123"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_notification_repository_create_notification(async_db_session) -> None:
    """Test NotificationRepository creates new notification.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    video_repo = VideoRepository(async_db_session)
    notif_repo = NotificationRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id="123",
        chat_type="private",
        title="test",
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )
    video = await video_repo.create_video(
        video_id="test123",
        channel_id=channel.id,
        title="Test",
        description="Test",
        url="https://youtube.com/watch?v=test123",
        published_at=datetime(2024, 1, 1),
    )

    notification = await notif_repo.create_notification(
        chat_id=chat.id,
        video_id=video.id,
        message_id="telegram_msg_123",
    )

    assert notification.id is not None
    assert notification.chat_id == chat.id
    assert notification.video_id == video.id
    assert notification.message_id == "telegram_msg_123"


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_notification_repository_get_chat_notifications(async_db_session) -> None:
    """Test NotificationRepository retrieves chat notifications.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    video_repo = VideoRepository(async_db_session)
    notif_repo = NotificationRepository(async_db_session)

    await user_repo.get_or_create_user(telegram_id="123", username="test")
    chat = await chat_repo.get_or_create_chat(
        chat_id="123",
        chat_type="private",
        title="test",
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )
    video1 = await video_repo.create_video(
        video_id="video1",
        channel_id=channel.id,
        title="Video 1",
        description="Test",
        url="https://youtube.com/watch?v=video1",
        published_at=datetime(2024, 1, 1),
    )
    video2 = await video_repo.create_video(
        video_id="video2",
        channel_id=channel.id,
        title="Video 2",
        description="Test",
        url="https://youtube.com/watch?v=video2",
        published_at=datetime(2024, 1, 2),
    )

    await notif_repo.create_notification(chat.id, video1.id)
    await notif_repo.create_notification(chat.id, video2.id)

    notifications = await notif_repo.get_chat_notifications(chat.id)

    assert len(notifications) == 2
    # Should be ordered by sent_at desc, so most recent first
    assert notifications[0].video_id == video2.id
    assert notifications[1].video_id == video1.id


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_repository_webhook_metadata_crud(async_db_session):
    """Ensure webhook lease metadata can be recorded and cleared."""
    channel_repo = ChannelRepository(async_db_session)
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCleases",
        channel_name="Lease Channel",
        channel_url="https://youtube.com/channel/UCleases",
    )

    expires_at = datetime.now(UTC) + timedelta(hours=24)
    recorded = await channel_repo.record_webhook_verification(
        channel_id=channel.channel_id,
        callback_url="https://bot.example/webhook/youtube",
        lease_seconds=86400,
        lease_expires_at=expires_at,
        last_verified_at=datetime.now(UTC),
    )
    assert recorded is True

    refreshed = await channel_repo.get_channel_by_id("UCleases")
    assert refreshed is not None
    assert refreshed.webhook_callback_url == "https://bot.example/webhook/youtube"
    assert refreshed.webhook_lease_seconds == 86400
    assert refreshed.webhook_lease_expires_at == expires_at

    cleared = await channel_repo.clear_webhook_metadata(
        channel_id="UCleases",
    )
    assert cleared is True
    # Re-fetch the channel after clearing metadata
    refreshed_after_clear = await channel_repo.get_channel_by_id("UCleases")
    assert refreshed_after_clear is not None
    assert refreshed_after_clear.webhook_callback_url is None
    assert refreshed_after_clear.webhook_lease_seconds is None
    assert refreshed_after_clear.webhook_lease_expires_at is None
    assert refreshed_after_clear.webhook_last_verified_at is None


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_channel_repository_returns_lease_candidates(async_db_session):
    """Channels nearing expiry should surface as renewal candidates."""
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    chat = await chat_repo.get_or_create_chat(
        chat_id="lease-chat", chat_type="private", title="Lease Chat"
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCleaseCandidate",
        channel_name="Lease Candidate",
        channel_url="https://youtube.com/channel/UCleaseCandidate",
    )
    await sub_repo.create_subscription(chat.id, channel.id)

    soon_expiring = datetime.now(UTC) + timedelta(minutes=30)
    channel.webhook_callback_url = "https://bot.example/webhook"
    channel.webhook_lease_seconds = 3600
    channel.webhook_lease_expires_at = soon_expiring
    await async_db_session.commit()

    threshold = datetime.now(UTC) + timedelta(hours=2)
    candidates = await channel_repo.get_channels_ready_for_lease_renewal(threshold=threshold)
    assert len(candidates) == 1
    assert candidates[0].channel_id == "UCleaseCandidate"

    # Move expiry beyond threshold to ensure it no longer appears.
    channel.webhook_lease_expires_at = datetime.now(UTC) + timedelta(hours=4)
    await async_db_session.commit()

    candidates = await channel_repo.get_channels_ready_for_lease_renewal(threshold=threshold)
    assert candidates == []


@allure.feature("Database")
@allure.story("Repositories")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_subscription_repository_channel_has_active_subscribers(async_db_session):
    """Channel subscriber guard should respect exclusions."""
    chat_repo = ChatRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    chat = await chat_repo.get_or_create_chat(
        chat_id="guard-chat", chat_type="private", title="Guard Chat"
    )
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCguard",
        channel_name="Guard Channel",
        channel_url="https://youtube.com/channel/UCguard",
    )

    assert (await sub_repo.channel_has_active_subscribers(channel.id, request_id="test")) is False

    await sub_repo.create_subscription(chat.id, channel.id)
    assert await sub_repo.channel_has_active_subscribers(channel.id) is True
    assert (
        await sub_repo.channel_has_active_subscribers(
            channel.id,
            exclude_chat_id=chat.id,
        )
    ) is False
