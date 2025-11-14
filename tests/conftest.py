"""Pytest fixtures for testing.

This module provides shared fixtures for testing the YouTube Updater Telegram Bot.
Includes fixtures for database sessions, mock API clients, and bot instances.
"""

from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from telegram import Bot, Chat, Message, Update, User
from telegram.ext import Application, ContextTypes

from src.database.models import Base
from src.webhooks.pubsub import PubSubManager
from src.youtube.api import YouTubeAPI


@pytest.fixture(scope="function")
async def async_db_engine():
    """Create async in-memory SQLite engine for testing.

    Returns:
        AsyncEngine: SQLAlchemy async engine using in-memory SQLite.
    """
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        echo=False,
        future=True,
    )

    # Create all tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine

    # Cleanup
    await engine.dispose()


@pytest.fixture(scope="function")
async def async_db_session(async_db_engine) -> AsyncGenerator[AsyncSession]:
    """Create async database session for testing.

    Args:
        async_db_engine: Async database engine fixture.

    Yields:
        AsyncSession: SQLAlchemy async session for test database operations.
    """
    async_session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with async_session_maker() as session:
        yield session
        await session.rollback()


@pytest.fixture
def mock_telegram_bot() -> MagicMock:
    """Create mock Telegram bot instance.

    Returns:
        MagicMock: Mock Bot instance with common methods mocked.
    """
    bot = MagicMock(spec=Bot)
    bot.send_message = AsyncMock()
    bot.edit_message_text = AsyncMock()
    bot.answer_callback_query = AsyncMock()
    bot.delete_message = AsyncMock()
    bot.get_chat = AsyncMock()
    bot.get_chat_member = AsyncMock()

    # Set bot properties
    bot.id = 12345678
    bot.username = "test_bot"
    bot.first_name = "Test Bot"

    return bot


@pytest.fixture
def mock_telegram_application(mock_telegram_bot) -> MagicMock:
    """Create mock Telegram Application instance.

    Args:
        mock_telegram_bot: Mock bot fixture.

    Returns:
        MagicMock: Mock Application instance.
    """
    app = MagicMock(spec=Application)
    app.bot = mock_telegram_bot
    return app


@pytest.fixture
def mock_telegram_update() -> MagicMock:
    """Create mock Telegram Update instance.

    Returns:
        MagicMock: Mock Update with message and user.
    """
    # Create mock user
    user = MagicMock(spec=User)
    user.id = 123456789
    user.username = "testuser"
    user.first_name = "Test"
    user.last_name = "User"
    user.is_bot = False

    # Create mock chat
    chat = MagicMock(spec=Chat)
    chat.id = 123456789
    chat.type = "private"
    chat.username = "testuser"
    chat.title = "Test Chat"

    # Create mock message
    message = MagicMock(spec=Message)
    message.message_id = 1
    message.from_user = user
    message.chat = chat
    message.text = ""
    message.reply_text = AsyncMock()
    message.reply_html = AsyncMock()
    message.edit_text = AsyncMock()
    message.edit_caption = AsyncMock()
    message.date = datetime.now(UTC)

    # Create mock update
    update = MagicMock(spec=Update)
    update.update_id = 1
    update.message = message
    update.effective_user = user
    update.effective_chat = chat
    update.effective_message = message
    update.callback_query = None

    return update


@pytest.fixture
def mock_telegram_context(mock_telegram_bot) -> MagicMock:
    """Create mock Telegram Context instance.

    Args:
        mock_telegram_bot: Mock bot fixture.

    Returns:
        MagicMock: Mock context for handlers.
    """
    context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
    context.bot = mock_telegram_bot
    context.args = []
    context.user_data = {}
    context.chat_data = {}
    context.bot_data = {}
    return context


@pytest.fixture
def mock_youtube_api() -> MagicMock:
    """Create mock YouTube API client.

    Returns:
        MagicMock: Mock YouTubeAPI instance with async methods.
    """
    api = MagicMock(spec=YouTubeAPI)

    # Mock channel info response
    async def mock_get_channel_info(channel_id: str):
        return {
            "id": channel_id,
            "snippet": {
                "title": "Test Channel",
                "customUrl": f"@{channel_id}",
            },
        }

    api.get_channel_info = AsyncMock(side_effect=mock_get_channel_info)
    api.extract_channel_id = MagicMock(return_value="UCtest123")
    api.extract_video_id = MagicMock(return_value="dQw4w9WgXcQ")
    api.close = AsyncMock()

    return api


@pytest.fixture
def mock_httpx_client() -> MagicMock:
    """Create mock httpx AsyncClient.

    Returns:
        MagicMock: Mock httpx.AsyncClient with common methods.
    """
    client = MagicMock(spec=httpx.AsyncClient)

    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"items": []})
    mock_response.text = ""
    mock_response.raise_for_status = MagicMock()

    client.get = AsyncMock(return_value=mock_response)
    client.post = AsyncMock(return_value=mock_response)
    client.aclose = AsyncMock()

    return client


@pytest.fixture
def mock_pubsub_manager(mock_httpx_client) -> MagicMock:
    """Create mock PubSubManager instance.

    Args:
        mock_httpx_client: Mock httpx client fixture.

    Returns:
        MagicMock: Mock PubSubManager with mocked methods.
    """
    manager = MagicMock(spec=PubSubManager)
    manager.client = mock_httpx_client
    manager.webhook_url = "https://example.com/webhook/youtube"
    manager.hub_url = "https://pubsubhubbub.appspot.com/subscribe"

    manager.subscribe_to_channel = AsyncMock(return_value=True)
    manager.unsubscribe_from_channel = AsyncMock(return_value=True)
    manager.get_topic_url = MagicMock(
        side_effect=lambda channel_id: (
            f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"
        )
    )
    manager.close = AsyncMock()

    return manager


@pytest.fixture
def sample_user_data() -> dict:
    """Sample user data for testing.

    Returns:
        dict: User data dictionary.
    """
    return {
        "telegram_id": "123456789",
        "username": "testuser",
        "first_name": "Test",
        "last_name": "User",
    }


@pytest.fixture
def sample_channel_data() -> dict:
    """Sample YouTube channel data for testing.

    Returns:
        dict: Channel data dictionary.
    """
    return {
        "channel_id": "UCtest123",
        "channel_name": "Test Channel",
        "channel_url": "https://www.youtube.com/channel/UCtest123",
        "feed_url": "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UCtest123",
    }


@pytest.fixture
def sample_video_data() -> dict:
    """Sample video data for testing.

    Returns:
        dict: Video data dictionary.
    """
    return {
        "video_id": "dQw4w9WgXcQ",
        "title": "Test Video",
        "description": "This is a test video",
        "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
        "published_at": datetime(2024, 1, 1, 12, 0, 0),
        "thumbnail_url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/default.jpg",
    }
