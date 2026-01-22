from collections.abc import Generator
from typing import Any, cast
from unittest.mock import ANY, AsyncMock, MagicMock, call, patch

import pytest
from telegram import Update
from telegram.ext import ContextTypes

from src.bot.bot import YouTubeUpdaterBot


@pytest.fixture
def mock_settings() -> Generator[Any]:
    with patch("src.bot.bot.settings") as mock_settings:
        mock_settings.telegram_bot_token = "TEST_TOKEN"
        mock_settings.default_locale = "en"
        mock_settings.pubsub_lease_renewal_threshold = 3600
        mock_settings.pubsub_lease_renewal_batch_limit = 100
        mock_settings.pubsub_lease_renewal_interval = 600
        mock_settings.webhook_callback_url = "http://test.url"
        yield mock_settings


@pytest.fixture
def mock_application_builder() -> Generator[Any]:
    with patch("src.bot.bot.Application.builder") as mock_builder:
        mock_app = AsyncMock()
        mock_app.add_error_handler = MagicMock()
        mock_app.add_handler = MagicMock()
        mock_builder.return_value.token.return_value.defaults.return_value.build.return_value = (
            mock_app
        )
        mock_builder.return_value.token.return_value.defaults.return_value.build.return_value.job_queue = MagicMock()
        yield mock_builder


@pytest.fixture
def mock_youtube_api() -> Generator[Any]:
    with patch("src.bot.bot.YouTubeAPI") as mock_api:
        yield mock_api


@pytest.fixture
def mock_notification_service() -> Generator[Any]:
    with patch("src.bot.bot.NotificationService") as mock_service:
        yield mock_service


@pytest.fixture
def mock_webhook_synchronizer() -> Generator[Any]:
    with patch("src.bot.bot.WebhookSubscriptionSynchronizer") as mock_synchronizer:
        mock_synchronizer.return_value.run = AsyncMock()
        yield mock_synchronizer


@pytest.fixture
def mock_webhook_lease_refresher() -> Generator[Any]:
    with patch("src.bot.bot.WebhookLeaseRefresher") as mock_refresher:
        mock_refresher.return_value.run = AsyncMock()
        yield mock_refresher


@pytest.fixture
def mock_setup_logging() -> Generator[Any]:
    with patch("src.bot.bot.setup_logging") as mock_logging:
        yield mock_logging


@pytest.fixture
def mock_init_db() -> Generator[Any]:
    with patch("src.bot.bot.init_db") as mock_db:
        yield mock_db


@pytest.fixture
def mock_setup_handlers() -> Generator[Any]:
    with patch("src.bot.bot.setup_handlers") as mock_handlers:
        yield mock_handlers


@pytest.fixture
def mock_translate() -> Generator[Any]:
    with patch("src.bot.bot.translate") as mock_trans:
        mock_trans.return_value = "Generic Error"
        yield mock_trans


@pytest.fixture
def mock_normalize_locale_code() -> Generator[Any]:
    with patch("src.bot.bot.normalize_locale_code") as mock_norm:
        mock_norm.side_effect = lambda x: x  # Simply return the input for testing
        yield mock_norm


@pytest.fixture
def mock_async_session_local() -> Generator[Any]:
    with patch("src.bot.bot.AsyncSessionLocal") as mock_session_local:
        yield mock_session_local


@pytest.mark.asyncio
async def test_initialize_success(
    mock_settings: Any,
    mock_application_builder: Any,
    mock_youtube_api: Any,
    mock_notification_service: Any,
    mock_webhook_synchronizer: Any,
    mock_webhook_lease_refresher: Any,
    mock_setup_logging: Any,
    mock_init_db: Any,
    mock_setup_handlers: Any,
    mock_async_session_local: Any,
) -> None:
    bot = YouTubeUpdaterBot()
    await bot.initialize()

    mock_setup_logging.assert_called_once()
    mock_init_db.assert_called_once()
    mock_webhook_synchronizer.assert_called_once_with(mock_async_session_local)
    mock_webhook_synchronizer.return_value.run.assert_awaited_once()
    mock_youtube_api.assert_called_once()
    mock_application_builder.assert_called_once()

    assert bot.application is not None
    app = cast(AsyncMock, bot.application)
    assert bot.youtube_api is not None
    assert bot.notification_service is not None
    assert bot.lease_refresher is not None

    mock_notification_service.assert_called_once_with(app.bot)
    mock_setup_handlers.assert_called_once_with(app, bot.youtube_api)

    # Verify error handler is added
    app.add_error_handler.assert_called_once()

    # Verify job queue scheduling
    assert app.job_queue is not None
    job_queue = cast(MagicMock, app.job_queue)  # Cast to MagicMock
    assert job_queue.run_repeating.call_count == 2
    # Check for heartbeat job
    mock_heartbeat_job_call = call(ANY, interval=300, first=10)
    mock_lease_refresh_job_call = call(
        ANY,
        interval=mock_settings.pubsub_lease_renewal_interval,
        first=mock_settings.pubsub_lease_renewal_interval // 2 or 30,
    )

    # Check if run_repeating was called with these arguments
    calls = job_queue.run_repeating.call_args_list
    assert mock_heartbeat_job_call in calls
    assert mock_lease_refresh_job_call in calls

    mock_webhook_lease_refresher.assert_called_once_with(
        mock_async_session_local,
        webhook_callback_url=mock_settings.webhook_callback_url,
        renewal_threshold_seconds=mock_settings.pubsub_lease_renewal_threshold,
        batch_limit=mock_settings.pubsub_lease_renewal_batch_limit,
    )
    mock_webhook_lease_refresher.return_value.run.assert_awaited_once()


@pytest.mark.asyncio
async def test_error_handler_sends_message_to_user_default_locale(
    mock_settings: Any,
    mock_application_builder: Any,
    mock_translate: Any,
    mock_normalize_locale_code: Any,
    mock_init_db: Any,
    mock_webhook_synchronizer: Any,
    mock_webhook_lease_refresher: Any,
) -> None:
    bot = YouTubeUpdaterBot()
    await bot.initialize()

    mock_update = AsyncMock(spec=Update)
    mock_update.effective_chat = AsyncMock()
    mock_update.effective_chat.id = 123
    assert mock_update.effective_user is not None
    mock_update.effective_user.language_code = None  # Simulate no language code

    mock_context: ContextTypes.DEFAULT_TYPE = MagicMock(bot=AsyncMock())  # Pass bot here
    mock_context.error = Exception("Test Error")

    # Get the error handler from the mock application
    # The actual error handler is the second argument of add_error_handler
    assert bot.application is not None
    app = cast(AsyncMock, bot.application)
    error_handler_func = app.add_error_handler.call_args[0][0]

    await error_handler_func(mock_update, mock_context)

    mock_translate.assert_called_once_with("errors.generic", locale=mock_settings.default_locale)
    casted_send_message = cast(AsyncMock, mock_context.bot.send_message)
    casted_send_message.assert_called_once_with(
        chat_id=mock_update.effective_chat.id,
        text=mock_translate.return_value,
    )
    mock_normalize_locale_code.assert_not_called()


@pytest.mark.asyncio
async def test_error_handler_sends_message_to_user_with_user_locale(
    mock_settings: Any,
    mock_application_builder: Any,
    mock_translate: Any,
    mock_normalize_locale_code: Any,
    mock_init_db: Any,
    mock_webhook_synchronizer: Any,
    mock_webhook_lease_refresher: Any,
) -> None:
    bot = YouTubeUpdaterBot()
    await bot.initialize()

    mock_update: Update = AsyncMock()
    assert mock_update.effective_chat is not None
    mock_update.effective_chat.id = 123
    assert mock_update.effective_user is not None
    mock_update.effective_user.language_code = "fr-CA"  # Simulate French Canadian locale

    mock_context: ContextTypes.DEFAULT_TYPE = MagicMock(bot=AsyncMock())  # Pass bot here
    mock_context.error = Exception("Test Error")

    assert bot.application is not None
    app = cast(AsyncMock, bot.application)
    error_handler_func = app.add_error_handler.call_args[0][0]

    await error_handler_func(mock_update, mock_context)

    mock_normalize_locale_code.assert_called_once_with(mock_update.effective_user.language_code)
    mock_translate.assert_called_once_with(
        "errors.generic", locale="fr-CA"
    )  # normalize_locale_code returns input
    casted_send_message = cast(AsyncMock, mock_context.bot.send_message)
    casted_send_message.assert_called_once_with(
        chat_id=mock_update.effective_chat.id,
        text=mock_translate.return_value,
    )


@pytest.mark.asyncio
async def test_error_handler_no_effective_chat(
    mock_settings: Any,
    mock_application_builder: Any,
    mock_translate: Any,
    mock_init_db: Any,
    mock_webhook_synchronizer: Any,
    mock_webhook_lease_refresher: Any,
) -> None:
    bot = YouTubeUpdaterBot()
    await bot.initialize()

    mock_update = AsyncMock(spec=Update)
    mock_update.effective_chat = None

    mock_context: ContextTypes.DEFAULT_TYPE = MagicMock(bot=AsyncMock())  # Pass bot here
    mock_context.error = Exception("Test Error")

    assert bot.application is not None
    app = cast(AsyncMock, bot.application)
    error_handler_func = app.add_error_handler.call_args[0][0]

    await error_handler_func(mock_update, mock_context)

    mock_translate.assert_not_called()
    casted_send_message = cast(AsyncMock, mock_context.bot.send_message)
    casted_send_message.assert_not_called()


@pytest.mark.asyncio
async def test_error_handler_send_message_fails(
    mock_settings: Any,
    mock_application_builder: Any,
    mock_translate: Any,
    caplog: Any,  # To capture logs
    mock_normalize_locale_code: Any,
    mock_init_db: Any,
    mock_webhook_synchronizer: Any,
    mock_webhook_lease_refresher: Any,
) -> None:
    bot = YouTubeUpdaterBot()
    await bot.initialize()

    mock_update: Update = AsyncMock()
    assert mock_update.effective_chat is not None
    mock_update.effective_chat.id = 123
    assert mock_update.effective_user is not None
    mock_update.effective_user.language_code = "es"

    mock_context: ContextTypes.DEFAULT_TYPE = MagicMock(bot=AsyncMock())  # Pass bot here
    mock_context.error = Exception("Test Error")
    casted_send_message = cast(AsyncMock, mock_context.bot.send_message)
    casted_send_message.side_effect = Exception("Telegram API Error")  # Simulate send failure

    assert bot.application is not None
    app = cast(AsyncMock, bot.application)
    error_handler_func = app.add_error_handler.call_args[0][0]

    with caplog.at_level(10):  # DEBUG level
        await error_handler_func(mock_update, mock_context)

    mock_normalize_locale_code.assert_called_once_with("es")
    mock_translate.assert_called_once_with("errors.generic", locale="es")
    casted_send_message.assert_called_once()
    assert "Could not send error message to user: Telegram API Error" in caplog.text
