import logging
from asyncio.exceptions import CancelledError

from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes, Defaults

from ..database.database import AsyncSessionLocal, init_db
from ..utils.config import settings
from ..utils.i18n import normalize_locale_code, translate
from ..utils.logging import setup_logging
from ..webhooks.lease_refresher import WebhookLeaseRefresher
from ..webhooks.synchronizer import WebhookSubscriptionSynchronizer
from ..youtube.api import YouTubeAPI
from .handlers import setup_handlers
from .notifications import NotificationService


logger = logging.getLogger(__name__)


class YouTubeUpdaterBot:
    """Main bot application class."""

    def __init__(self) -> None:
        self.application: Application | None = None
        self.youtube_api: YouTubeAPI | None = None
        self.notification_service: NotificationService | None = None
        self.lease_refresher: WebhookLeaseRefresher | None = None

    async def initialize(self) -> None:
        """Initialize the bot and all its components."""
        try:
            # Setup logging
            setup_logging()
            logger.info("Starting YouTube Updater Bot...")

            # Initialize database
            logger.info("Initializing database...")
            await init_db()
            logger.info("Database initialized")

            synchronizer = WebhookSubscriptionSynchronizer(AsyncSessionLocal)
            await synchronizer.run()

            # Create YouTube API client
            self.youtube_api = YouTubeAPI()
            logger.info("YouTube API client created")

            # Create Telegram bot application
            defaults = Defaults(parse_mode=ParseMode.MARKDOWN_V2)
            self.application = (
                Application.builder()
                .token(settings.telegram_bot_token)
                .defaults(defaults)
                .build()
            )
            if self.application is None:
                raise RuntimeError("Failed to create Telegram application")

            # Create notification service
            self.notification_service = NotificationService(self.application.bot)

            # Setup error handler
            async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
                """Log errors caused by Updates."""
                logger.error(
                    f"Exception while handling an update: {context.error}", exc_info=context.error
                )

                # Try to send error message to user if possible
                if hasattr(update, "effective_chat") and update.effective_chat:
                    locale = settings.default_locale
                    if hasattr(update, "effective_user") and hasattr(
                        update.effective_user, "language_code"
                    ):
                        language_code = getattr(update.effective_user, "language_code", None)
                        if language_code:
                            normalized = normalize_locale_code(language_code)
                            if normalized:
                                locale = normalized

                    try:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=translate("errors.generic", locale=locale),
                        )
                    except Exception as e:
                        logger.error(f"Could not send error message to user: {e}")

            self.application.add_error_handler(error_handler)

            # Setup handlers
            if self.youtube_api is None:
                raise RuntimeError("YouTube API client is not initialized")
            setup_handlers(self.application, self.youtube_api)
            logger.info("Bot handlers configured")

            # Add periodic job for heartbeat logging

            job_queue = self.application.job_queue

            async def heartbeat_callback(context: ContextTypes.DEFAULT_TYPE) -> None:
                """Periodic heartbeat logging."""
                logger.info("Bot heartbeat - actively running and processing updates")

            if job_queue:
                job_queue.run_repeating(
                    heartbeat_callback, interval=300, first=10
                )  # Every 5 minutes
                logger.info("Heartbeat logging job scheduled")

                self.lease_refresher = WebhookLeaseRefresher(
                    AsyncSessionLocal,
                    webhook_callback_url=settings.webhook_callback_url,
                    renewal_threshold_seconds=settings.pubsub_lease_renewal_threshold,
                    batch_limit=settings.pubsub_lease_renewal_batch_limit or None,
                )

                await self.lease_refresher.run()

                async def lease_refresh_job(context: ContextTypes.DEFAULT_TYPE) -> None:
                    if self.lease_refresher:
                        await self.lease_refresher.run()

                job_queue.run_repeating(
                    lease_refresh_job,
                    interval=settings.pubsub_lease_renewal_interval,
                    first=settings.pubsub_lease_renewal_interval // 2 or 30,
                )
                logger.info(
                    "Webhook lease refresher scheduled",
                    extra={
                        "meta_interval": settings.pubsub_lease_renewal_interval,
                        "meta_threshold": settings.pubsub_lease_renewal_threshold,
                    },
                )

            logger.info("Bot initialization completed successfully")

        except Exception as e:
            logger.error(f"Error during bot initialization: {e}")
            raise

    def run(self) -> None:
        """Run the bot using run_polling (blocking)."""
        try:
            logger.info("Bot is now starting to poll for updates...")

            # If not already initialized, initialize first
            if not self.application:
                import asyncio

                # Create an event loop and keep it for run_polling to use
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)

                # Initialize in this loop
                loop.run_until_complete(self.initialize())
                logger.info("Bot initialized successfully")
            else:
                logger.info("Bot already initialized, starting polling...")

            # Use run_polling which will use the existing event loop
            if self.application is None:
                raise RuntimeError("Application failed to initialize")
            self.application.run_polling(drop_pending_updates=True)

        except (KeyboardInterrupt, CancelledError):
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Unexpected error: {e}", exc_info=True)
            raise
        finally:
            logger.info("Bot execution completed")

    async def stop(self) -> None:
        """Stop the Telegram application if running."""
        if self.application:
            await self.application.stop()

    async def cleanup(self) -> None:
        """Shutdown Telegram application resources."""
        if self.application:
            await self.application.shutdown()
