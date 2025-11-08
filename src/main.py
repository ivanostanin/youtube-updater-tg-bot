import logging

import uvicorn

from .bot.bot import YouTubeUpdaterBot
from .storage.startup import ensure_database_backup
from .utils.config import settings
from .utils.logging import setup_logging
from .webhooks.handlers import create_webhook_app


logger = logging.getLogger(__name__)


class Application:
    """Main application that runs both the Telegram bot and webhook server."""

    def __init__(self):
        self.bot = YouTubeUpdaterBot()
        self.webhook_app = None

    async def setup(self):
        """Setup the application."""
        setup_logging()
        logger.info("Setting up YouTube Updater Bot application...")

        # Initialize the bot
        await self.bot.initialize()

        # Create webhook app
        self.webhook_app = create_webhook_app(self.bot.notification_service)

        logger.info("Application setup completed")

    def start_bot(self):
        """Start the Telegram bot."""
        try:
            logger.info("Starting Telegram bot...")
            self.bot.run()
        except Exception as e:
            logger.error(f"Error running bot: {e}")
            raise

    def start_webhook_server(self):
        """Start the webhook server."""
        try:
            logger.info(
                f"Starting webhook server on {settings.webhook_host}:{settings.webhook_port}"
            )

            # Configure uvicorn to not mess with logging
            config = uvicorn.Config(
                self.webhook_app,
                host=settings.webhook_host,
                port=settings.webhook_port,
                log_level=settings.log_level.lower(),
                access_log=True,
                log_config=None,  # Don't override our logging config
            )
            server = uvicorn.Server(config)
            server.run()

        except Exception as e:
            logger.error(f"Error starting webhook server: {e}")
            raise

    def run(self):
        """Run both bot and webhook server concurrently."""
        try:
            # Setup logging first (synchronously)
            setup_logging()
            logger.info("Setting up YouTube Updater Bot application...")

            ensure_database_backup(settings.database_url)

            # Initialize bot first to get notification service
            import asyncio

            asyncio.run(self.setup())
            logger.info("Bot and webhook app setup completed")

            # Start webhook server in background thread
            import threading

            webhook_thread = threading.Thread(target=self.start_webhook_server)
            webhook_thread.daemon = True
            webhook_thread.start()
            logger.info("Webhook server thread started")

            # Give webhook server time to start
            import time

            time.sleep(1)

            # Let the bot handle its own polling in main thread
            logger.info("Starting bot in main thread...")
            self.start_bot()

        except KeyboardInterrupt:
            logger.info("Received shutdown signal")
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            raise

    async def cleanup(self):
        """Cleanup resources."""
        try:
            logger.info("Cleaning up...")
            await self.bot.stop()
            await self.bot.cleanup()
            logger.info("Cleanup completed")
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")


def main():
    """Main entry point."""
    app = Application()
    app.run()


if __name__ == "__main__":
    main()
