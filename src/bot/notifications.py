from telegram import Bot
from telegram.error import TelegramError

from ..database.models import Video, YouTubeChannel
from ..utils.formatters import format_group_discussion_prompt
from ..utils.i18n import translate
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
        locale: str,
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
                locale=locale,
                request_id=correlation_id,
            )

            sent_message = await self.bot.send_message(
                chat_id=chat_telegram_id,
                text=message,
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
        locale: str,
        request_id: str | None = None,
    ) -> str:
        """Format a video notification message."""
        title = video.title if len(video.title) <= 100 else f"{video.title[:97]}..."

        description = (video.description or "").strip()
        if len(description) > 200:
            description = f"{description[:197]}..."

        message_parts = [
            translate("notifications.video.heading", locale=locale, request_id=request_id),
            "",
            translate(
                "notifications.video.channel",
                locale=locale,
                request_id=request_id,
                channel_name=channel.channel_name,
            ),
            translate(
                "notifications.video.video",
                locale=locale,
                request_id=request_id,
                video_title=title,
            ),
        ]

        if description:
            message_parts.extend(
                [
                    translate(
                        "notifications.video.description",
                        locale=locale,
                        request_id=request_id,
                        video_description=description,
                    ),
                    "",
                ]
            )

        message_parts.extend(
            [
                translate(
                    "notifications.video.watch",
                    locale=locale,
                    request_id=request_id,
                    video_url=video.url,
                ),
                "",
                translate(
                    "notifications.video.published",
                    locale=locale,
                    request_id=request_id,
                    published_at=video.published_at.strftime("%B %d, %Y at %I:%M %p UTC"),
                ),
            ]
        )

        group_prompt = format_group_discussion_prompt(
            chat_type=chat_type,
            chat_title=chat_title,
            locale=locale,
            request_id=request_id,
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
        locale: str,
        request_id: str | None = None,
    ) -> int | None:
        """Send subscription confirmation message."""
        correlation_id = request_id or new_request_id()
        try:
            intro_key = (
                "notifications.subscription.private_title"
                if chat_type == "private"
                else "notifications.subscription.shared_title"
            )
            context_key = (
                "notifications.subscription.private_body"
                if chat_type == "private"
                else "notifications.subscription.shared_body"
            )

            intro = translate(intro_key, locale=locale, request_id=correlation_id)
            audience = chat_title
            if chat_type != "private":
                audience = audience or translate(
                    "notifications.subscription.default_audience",
                    locale=locale,
                    request_id=correlation_id,
                )
            context_line = translate(
                context_key,
                locale=locale,
                request_id=correlation_id,
                chat_title=audience or "",
            )

            message = translate(
                "notifications.subscription.message",
                locale=locale,
                request_id=correlation_id,
                intro=intro,
                channel_name=channel.channel_name,
                context_line=context_line,
                channel_url=channel.channel_url,
            )

            sent_message = await self.bot.send_message(
                chat_id=chat_telegram_id,
                text=message,
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
        locale: str,
        request_id: str | None = None,
    ) -> int | None:
        """Send error notification to chat."""
        correlation_id = request_id or new_request_id()
        try:
            message = translate(
                "notifications.error",
                locale=locale,
                request_id=correlation_id,
                error_message=error_message,
            )

            sent_message = await self.bot.send_message(
                chat_id=chat_telegram_id,
                text=message,
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
