import logging

from telegram import Bot
from telegram.error import TelegramError

from ..database.models import Video, YouTubeChannel


logger = logging.getLogger(__name__)


class NotificationService:
    """Service for sending Telegram notifications."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_video_notification(
        self, user_telegram_id: str, video: Video, channel: YouTubeChannel
    ) -> int | None:
        """Send a video notification to a user."""
        try:
            # Format the notification message
            message = self.format_video_message(video, channel)

            # Send the message
            sent_message = await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )

            logger.info(f"Sent video notification to user {user_telegram_id}: {video.title}")
            return sent_message.message_id

        except TelegramError as e:
            logger.error(f"Telegram error sending notification to {user_telegram_id}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error sending notification to {user_telegram_id}: {e}")
            return None

    def format_video_message(self, video: Video, channel: YouTubeChannel) -> str:
        """Format a video notification message."""
        # Truncate title if too long
        title = video.title
        if len(title) > 100:
            title = title[:97] + "..."

        # Truncate description if too long
        description = video.description or ""
        if len(description) > 200:
            description = description[:197] + "..."

        message_parts = [
            "🎬 **New Video Alert!**",
            "",
            f"📺 **Channel:** {channel.channel_name}",
            f"🎥 **Video:** {title}",
        ]

        if description:
            message_parts.extend([f"📝 **Description:** {description}", ""])

        message_parts.extend(
            [
                f"🔗 **Watch:** {video.url}",
                "",
                f"📅 Published: {video.published_at.strftime('%B %d, %Y at %I:%M %p UTC')}",
            ]
        )

        return "\n".join(message_parts)

    async def send_subscription_confirmation(
        self, user_telegram_id: str, channel: YouTubeChannel
    ) -> int | None:
        """Send subscription confirmation message."""
        try:
            message = (
                f"✅ **Subscription Confirmed!**\n\n"
                f"You're now subscribed to **{channel.channel_name}**\n\n"
                f"You'll receive notifications when new videos are uploaded.\n\n"
                f"Channel: {channel.channel_url}"
            )

            sent_message = await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

            return sent_message.message_id

        except TelegramError as e:
            logger.error(f"Error sending subscription confirmation to {user_telegram_id}: {e}")
            return None

    async def send_error_notification(
        self, user_telegram_id: str, error_message: str
    ) -> int | None:
        """Send error notification to user."""
        try:
            message = f"❌ **Error:** {error_message}"

            sent_message = await self.bot.send_message(
                chat_id=user_telegram_id,
                text=message,
                parse_mode="Markdown",
            )

            return sent_message.message_id

        except TelegramError as e:
            logger.error(f"Error sending error notification to {user_telegram_id}: {e}")
            return None
