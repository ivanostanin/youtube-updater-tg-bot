from telegram import Bot
from telegram.error import TelegramError

from ..database.models import Video, YouTubeChannel
from ..utils.formatters import format_group_discussion_prompt
from ..utils.logging import get_logger, log_context, new_request_id, sanitize_label


logger = get_logger(__name__)


class NotificationService:
    """Service for sending Telegram notifications."""

    def __init__(self, bot: Bot):
        self.bot = bot

    async def send_video_notification(
        self,
        chat_telegram_id: str,
        video: Video,
        channel: YouTubeChannel,
        *,
        chat_title: str | None,
        chat_type: str,
        request_id: str | None = None,
    ) -> int | None:
        """Send a video notification to a chat."""
        correlation_id = request_id or new_request_id()
        try:
            message = self.format_video_message(
                video,
                channel,
                chat_title=chat_title,
                chat_type=chat_type,
            )

            sent_message = await self.bot.send_message(
                chat_id=chat_telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=False,
            )

            logger.info(
                "Sent video notification",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_video",
                    chat_id=chat_telegram_id,
                    chat_type=chat_type,
                    video_id=video.video_id,
                    channel_id=channel.channel_id,
                    meta_chat_title=sanitize_label(chat_title),
                    meta_video_title=sanitize_label(video.title),
                    meta_channel_title=sanitize_label(channel.channel_name),
                ),
            )
            return sent_message.message_id

        except TelegramError as error:
            logger.error(
                "Telegram error sending video notification",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_video",
                    chat_id=chat_telegram_id,
                    chat_type=chat_type,
                    video_id=video.video_id,
                    channel_id=channel.channel_id,
                    meta_error=sanitize_label(str(error)),
                ),
            )
            return None
        except Exception as error:
            logger.error(
                "Unexpected error sending video notification",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_video",
                    chat_id=chat_telegram_id,
                    chat_type=chat_type,
                    video_id=video.video_id,
                    channel_id=channel.channel_id,
                    meta_error=sanitize_label(str(error)),
                ),
            )
            return None

    def format_video_message(
        self,
        video: Video,
        channel: YouTubeChannel,
        *,
        chat_title: str | None,
        chat_type: str,
    ) -> str:
        """Format a video notification message."""
        title = video.title if len(video.title) <= 100 else f"{video.title[:97]}..."

        description = (video.description or "").strip()
        if len(description) > 200:
            description = f"{description[:197]}..."

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

        group_prompt = format_group_discussion_prompt(
            chat_type=chat_type,
            chat_title=chat_title,
        )
        if group_prompt:
            message_parts.extend(["", group_prompt])

        return "\n".join(message_parts)

    async def send_subscription_confirmation(
        self,
        chat_telegram_id: str,
        channel: YouTubeChannel,
        *,
        chat_title: str | None,
        chat_type: str,
        request_id: str | None = None,
    ) -> int | None:
        """Send subscription confirmation message."""
        correlation_id = request_id or new_request_id()
        try:
            if chat_type == "private":
                intro = "✅ **Subscription Confirmed!**"
                context_line = "You'll receive notifications when new videos are uploaded."
            else:
                intro = "✅ **Chat Subscription Activated!**"
                audience = chat_title or "this chat"
                context_line = (
                    f"Everyone in {audience} will see updates from this YouTube channel."
                )

            message = (
                f"{intro}\n\n"
                f"**Channel:** {channel.channel_name}\n"
                f"{context_line}\n\n"
                f"Channel URL: {channel.channel_url}"
            )

            sent_message = await self.bot.send_message(
                chat_id=chat_telegram_id,
                text=message,
                parse_mode="Markdown",
                disable_web_page_preview=True,
            )

            logger.info(
                "Sent subscription confirmation",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_subscription_confirmation",
                    chat_id=chat_telegram_id,
                    chat_type=chat_type,
                    channel_id=channel.channel_id,
                    meta_chat_title=sanitize_label(chat_title),
                    meta_channel_title=sanitize_label(channel.channel_name),
                ),
            )
            return sent_message.message_id

        except TelegramError as error:
            logger.error(
                "Error sending subscription confirmation",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_subscription_confirmation",
                    chat_id=chat_telegram_id,
                    chat_type=chat_type,
                    channel_id=channel.channel_id,
                    meta_error=sanitize_label(str(error)),
                ),
            )
            return None

    async def send_error_notification(
        self,
        chat_telegram_id: str,
        error_message: str,
        *,
        request_id: str | None = None,
    ) -> int | None:
        """Send error notification to chat."""
        correlation_id = request_id or new_request_id()
        try:
            message = f"❌ **Error:** {error_message}"

            sent_message = await self.bot.send_message(
                chat_id=chat_telegram_id,
                text=message,
                parse_mode="Markdown",
            )

            logger.info(
                "Sent error notification",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_error",
                    chat_id=chat_telegram_id,
                    meta_error_message=sanitize_label(error_message),
                ),
            )
            return sent_message.message_id

        except TelegramError as error:
            logger.error(
                "Error sending error notification",
                extra=log_context(
                    request_id=correlation_id,
                    operation="notification.send_error",
                    chat_id=chat_telegram_id,
                    chat_type=None,
                    meta_error_message=sanitize_label(error_message),
                    meta_error=sanitize_label(str(error)),
                ),
            )
            return None
