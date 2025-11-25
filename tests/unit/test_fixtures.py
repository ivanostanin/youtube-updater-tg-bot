"""Test fixtures to verify test infrastructure works correctly.

This module contains basic tests to ensure that all test fixtures
are properly configured and functional.
"""

from unittest.mock import MagicMock

import allure
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User as DBUser  # Renamed to avoid conflict


@allure.feature("Test Infrastructure")
@allure.story("Fixtures")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
async def test_async_db_session_fixture(async_db_session: AsyncSession) -> None:
    """Test that async database session fixture works correctly.

    Args:
        async_db_session: Async database session fixture.
    """
    # Verify session is created
    assert async_db_session is not None

    # Test basic database operation
    user = DBUser(
        telegram_id="123456789",
        username="testuser",
        first_name="Test",
        last_name="User",
    )
    async_db_session.add(user)
    await async_db_session.commit()

    # Verify user was saved
    result = await async_db_session.execute(select(DBUser).where(DBUser.telegram_id == "123456789"))
    saved_user = result.scalar_one_or_none()

    assert saved_user is not None
    assert saved_user.username == "testuser"
    assert saved_user.first_name == "Test"


@allure.feature("Test Infrastructure")
@allure.story("Fixtures")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_mock_telegram_bot_fixture(mock_telegram_bot: MagicMock) -> None:
    """Test that mock Telegram bot fixture works correctly.

    Args:
        mock_telegram_bot: Mock Telegram bot fixture.
    """
    assert mock_telegram_bot is not None
    assert mock_telegram_bot.id == 12345678
    assert mock_telegram_bot.username == "test_bot"
    assert hasattr(mock_telegram_bot, "send_message")
    assert hasattr(mock_telegram_bot, "get_chat_member")


@allure.feature("Test Infrastructure")
@allure.story("Fixtures")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_mock_telegram_update_fixture(mock_telegram_update: MagicMock) -> None:
    """Test that mock Telegram update fixture works correctly.

    Args:
        mock_telegram_update: Mock Telegram update fixture.
    """
    assert mock_telegram_update is not None
    assert mock_telegram_update.message is not None
    assert mock_telegram_update.effective_user is not None
    assert mock_telegram_update.effective_user.id == 123456789
    assert mock_telegram_update.effective_chat.id == 123456789


@allure.feature("Test Infrastructure")
@allure.story("Fixtures")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_mock_youtube_api_fixture(mock_youtube_api: MagicMock) -> None:
    """Test that mock YouTube API fixture works correctly.

    Args:
        mock_youtube_api: Mock YouTube API fixture.
    """
    assert mock_youtube_api is not None
    assert hasattr(mock_youtube_api, "get_channel_info")
    assert hasattr(mock_youtube_api, "extract_channel_id")
    assert mock_youtube_api.extract_channel_id.return_value == "UCtest123"


@allure.feature("Test Infrastructure")
@allure.story("Fixtures")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_mock_pubsub_manager_fixture(mock_pubsub_manager: MagicMock) -> None:
    """Test that mock PubSubManager fixture works correctly.

    Args:
        mock_pubsub_manager: Mock PubSubManager fixture.
    """
    assert mock_pubsub_manager is not None
    assert mock_pubsub_manager.webhook_url == "https://example.com/webhook/youtube"
    assert hasattr(mock_pubsub_manager, "subscribe_to_channel")
    assert hasattr(mock_pubsub_manager, "get_topic_url")

    # Test topic URL generation
    topic_url = mock_pubsub_manager.get_topic_url("UCtest123")
    assert "UCtest123" in topic_url


@allure.feature("Test Infrastructure")
@allure.story("Fixtures")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_sample_data_fixtures(
    sample_user_data: dict, sample_channel_data: dict, sample_video_data: dict
) -> None:
    """Test that sample data fixtures are properly structured.

    Args:
        sample_user_data: Sample user data fixture.
        sample_channel_data: Sample channel data fixture.
        sample_video_data: Sample video data fixture.
    """
    # Verify user data
    assert sample_user_data["telegram_id"] == "123456789"
    assert sample_user_data["username"] == "testuser"

    # Verify channel data
    assert sample_channel_data["channel_id"] == "UCtest123"
    assert sample_channel_data["channel_name"] == "Test Channel"

    # Verify video data
    assert sample_video_data["video_id"] == "dQw4w9WgXcQ"
    assert sample_video_data["title"] == "Test Video"
    assert sample_video_data["url"] is not None
