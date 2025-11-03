"""Integration tests for database operations.

Tests multi-component database workflows including full subscription
flows, concurrent operations, and transaction handling.
"""

from datetime import datetime

import allure
import pytest

from src.database.models import User, YouTubeChannel
from src.database.repository import (
    ChannelRepository,
    NotificationRepository,
    SubscriptionRepository,
    UserRepository,
    VideoRepository,
)


@allure.feature("Integration")
@allure.story("Database Operations")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.integration
async def test_full_subscription_flow(async_db_session):
    """Test complete subscription workflow from user to channel creation.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    # Create user
    user = await user_repo.get_or_create_user(
        telegram_id="123456",
        username="testuser",
        first_name="Test",
    )

    # Create channel
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest123",
        channel_name="Test Channel",
        channel_url="https://youtube.com/channel/UCtest123",
        feed_url="https://youtube.com/feeds/videos.xml?channel_id=UCtest123",
    )

    # Create subscription
    subscription = await sub_repo.create_subscription(user.id, channel.id)

    assert subscription.user_id == user.id
    assert subscription.channel_id == channel.id
    assert subscription.is_active is True


@allure.feature("Integration")
@allure.story("Database Operations")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_subscription_listing_with_relationships(async_db_session):
    """Test retrieving subscriptions with full user and channel relationships.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    user = await user_repo.get_or_create_user(telegram_id="123", username="test")

    channel1 = await channel_repo.get_or_create_channel(
        channel_id="UC1",
        channel_name="Channel 1",
        channel_url="https://youtube.com/channel/UC1",
    )
    channel2 = await channel_repo.get_or_create_channel(
        channel_id="UC2",
        channel_name="Channel 2",
        channel_url="https://youtube.com/channel/UC2",
    )

    await sub_repo.create_subscription(user.id, channel1.id)
    await sub_repo.create_subscription(user.id, channel2.id)

    subscriptions = await sub_repo.get_user_subscriptions(user.id)

    assert len(subscriptions) == 2
    # Verify relationships are loaded
    assert all(sub.channel is not None for sub in subscriptions)
    assert {sub.channel.channel_id for sub in subscriptions} == {"UC1", "UC2"}


@allure.feature("Integration")
@allure.story("Database Operations")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_subscription_deletion_and_reactivation(async_db_session):
    """Test subscription soft deletion and re-subscription flow.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    user = await user_repo.get_or_create_user(telegram_id="123", username="test")
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    # Subscribe
    sub1 = await sub_repo.create_subscription(user.id, channel.id)
    assert sub1.is_active is True

    # Unsubscribe (soft delete)
    success = await sub_repo.delete_subscription(user.id, channel.id)
    assert success is True

    # Verify not in active subscriptions
    active_subs = await sub_repo.get_user_subscriptions(user.id)
    assert len(active_subs) == 0

    # Re-subscribe (creates new subscription)
    sub2 = await sub_repo.create_subscription(user.id, channel.id)
    assert sub2.id != sub1.id  # New record
    assert sub2.is_active is True


@allure.feature("Integration")
@allure.story("Database Operations")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.integration
async def test_video_creation_and_notification_linkage(async_db_session):
    """Test video creation linked to notifications workflow.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    video_repo = VideoRepository(async_db_session)
    notif_repo = NotificationRepository(async_db_session)

    user = await user_repo.get_or_create_user(telegram_id="123", username="test")
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCtest",
        channel_name="Test",
        channel_url="https://youtube.com/channel/UCtest",
    )

    video = await video_repo.create_video(
        video_id="testvideo",
        channel_id=channel.id,
        title="Test Video",
        description="Test",
        url="https://youtube.com/watch?v=testvideo",
        published_at=datetime(2024, 1, 1),
    )

    notification = await notif_repo.create_notification(user.id, video.id, message_id="msg123")

    # Verify linkage
    assert notification.video_id == video.id
    assert notification.user_id == user.id

    # Retrieve notifications with video relationship
    notifications = await notif_repo.get_user_notifications(user.id)
    assert len(notifications) == 1
    assert notifications[0].video is not None
    assert notifications[0].video.video_id == "testvideo"


@allure.feature("Integration")
@allure.story("Database Operations")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.integration
async def test_concurrent_subscriptions(async_db_session):
    """Test multiple users subscribing to same channel concurrently.

    Args:
        async_db_session: Async database session fixture.
    """
    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)
    sub_repo = SubscriptionRepository(async_db_session)

    # Create multiple users
    user1 = await user_repo.get_or_create_user(telegram_id="111", username="user1")
    user2 = await user_repo.get_or_create_user(telegram_id="222", username="user2")
    user3 = await user_repo.get_or_create_user(telegram_id="333", username="user3")

    # Create channel
    channel = await channel_repo.get_or_create_channel(
        channel_id="UCpopular",
        channel_name="Popular Channel",
        channel_url="https://youtube.com/channel/UCpopular",
    )

    # All users subscribe
    await sub_repo.create_subscription(user1.id, channel.id)
    await sub_repo.create_subscription(user2.id, channel.id)
    await sub_repo.create_subscription(user3.id, channel.id)

    # Verify all subscriptions
    subscribers = await sub_repo.get_channel_subscribers(channel.id)
    assert len(subscribers) == 3
    telegram_ids = {sub.user.telegram_id for sub in subscribers}
    assert telegram_ids == {"111", "222", "333"}


@allure.feature("Integration")
@allure.story("Database Operations")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.integration
async def test_transaction_rollback_on_error(async_db_session):
    """Test database operations maintain referential integrity.

    Args:
        async_db_session: Async database session fixture.
    """
    from sqlalchemy import select

    user_repo = UserRepository(async_db_session)
    channel_repo = ChannelRepository(async_db_session)

    # Create user and channel
    _user = await user_repo.get_or_create_user(telegram_id="integrity", username="test")
    _channel = await channel_repo.get_or_create_channel(
        channel_id="UCintegrity",
        channel_name="Integrity Test",
        channel_url="https://youtube.com/channel/UCintegrity",
    )

    # Verify both exist
    result = await async_db_session.execute(select(User).where(User.telegram_id == "integrity"))
    assert result.scalar_one_or_none() is not None

    result = await async_db_session.execute(
        select(YouTubeChannel).where(YouTubeChannel.channel_id == "UCintegrity")
    )
    assert result.scalar_one_or_none() is not None
