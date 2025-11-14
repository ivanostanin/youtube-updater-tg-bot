import logging
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from telegram import (
    Bot as TelegramBot,
)
from telegram import (
    Chat as TelegramChat,
)
from telegram import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Update,
)
from telegram import (
    User as TelegramUser,
)
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from ..database.database import AsyncSessionLocal
from ..database.models import Chat as DBChat
from ..database.models import User
from ..database.repository import (
    ChannelRepository,
    ChatRepository,
    SubscriptionRepository,
    UserRepository,
)
from ..services import ACLService
from ..utils.config import settings
from ..webhooks.pubsub import PubSubManager
from ..youtube.api import YouTubeAPI


logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(
        self,
        youtube_api: YouTubeAPI,
        bot: TelegramBot | None = None,
        acl_service: ACLService | None = None,
    ):
        self.youtube_api = youtube_api
        self.bot = bot
        self.webhook_manager = PubSubManager(webhook_url=settings.webhook_callback_url)
        self.acl_service = acl_service or (ACLService(bot) if bot is not None else None)

    async def manage_channel_webhook(self, channel_id: str, action: str = "subscribe") -> bool:
        """Manage webhook subscription for a YouTube channel."""
        try:
            logger.info("manage_channel_webhook: %s; channel_id: %s", action, channel_id)
            if action == "subscribe":
                success = await self.webhook_manager.subscribe_to_channel(channel_id)
            elif action == "unsubscribe":
                success = await self.webhook_manager.unsubscribe_from_channel(channel_id)
            else:
                logger.error("Unknown webhook action requested: %s", action)
                return False

            if success:
                logger.info("Webhook %s succeeded for channel %s", action, channel_id)
            else:
                logger.error("Webhook %s failed for channel %s", action, channel_id)
            return success
        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error managing webhook for channel %s: %s", channel_id, exc)
            return False

    async def check_if_channel_has_other_subscribers(
        self,
        session: AsyncSession,
        channel_id: int,
        exclude_chat_id: int | None = None,
    ) -> bool:
        """Check if a channel has active subscribers other than the provided chat."""
        subscription_repo = SubscriptionRepository(session)
        subscriptions = await subscription_repo.get_channel_subscribers(channel_id)
        return any(sub.chat_id != exclude_chat_id for sub in subscriptions)

    async def _ensure_chat_record(
        self,
        session: AsyncSession,
        *,
        telegram_chat: TelegramChat,
        db_user_id: int | None,
    ) -> DBChat:
        """Ensure there's a persisted chat entry for the Telegram chat."""
        chat_repo = ChatRepository(session)
        raw_title = (
            getattr(telegram_chat, "title", None)
            or getattr(telegram_chat, "username", None)
            or getattr(telegram_chat, "full_name", None)
            or getattr(telegram_chat, "first_name", None)
        )
        chat_title = str(raw_title) if raw_title is not None else None
        raw_type = getattr(telegram_chat, "type", None)
        chat_type = str(raw_type) if raw_type else "private"
        user_id = db_user_id if chat_type == "private" else None

        return await chat_repo.get_or_create_chat(
            chat_id=str(telegram_chat.id),
            chat_type=chat_type,
            title=chat_title,
            user_id=user_id,
        )

    async def _require_admin(
        self,
        *,
        telegram_chat: TelegramChat | None,
        telegram_user: TelegramUser | None,
        on_denied: Callable[[str], Awaitable[object]],
    ) -> bool:
        """Verify admin permissions for shared chat contexts."""
        if telegram_chat is None:
            await on_denied("I couldn't identify which chat triggered this command.")
            logger.warning("Missing chat context while enforcing admin requirement.")
            return False

        chat_type = getattr(telegram_chat, "type", "private") or "private"
        if not ACLService.is_group_context(chat_type):
            return True

        if self.acl_service is None:
            await on_denied(
                "I can't verify admin permissions for this chat right now. Please try again later."
            )
            logger.error("ACL service unavailable; denying group command execution.")
            return False

        chat_identifier: Any = getattr(telegram_chat, "id", None)
        if chat_identifier is None:
            await on_denied("I couldn't identify the target chat for this action.")
            logger.warning("Admin check aborted: chat id missing.")
            return False
        if isinstance(chat_identifier, (int, str)):
            chat_id: int | str = chat_identifier
        else:
            chat_id = str(chat_identifier)

        user_identifier: Any = getattr(telegram_user, "id", None) if telegram_user else None
        if isinstance(user_identifier, (int, str)) or user_identifier is None:
            user_id: int | str | None = user_identifier
        else:
            user_id = str(user_identifier)

        async def forward_denial(text: str) -> None:
            await on_denied(text)

        return await self.acl_service.require_admin(
            chat_id=chat_id,
            chat_type=chat_type,
            user_id=user_id,
            on_denied=forward_denial,
        )

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        user = update.effective_user
        message = update.message
        if user is None or message is None:
            logger.warning("Received /start without required user or message context")
            return

        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            db_user = await user_repo.get_or_create_user(
                telegram_id=str(user.id),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
            )
            if update.effective_chat:
                await self._ensure_chat_record(
                    session,
                    telegram_chat=update.effective_chat,
                    db_user_id=db_user.id,
                )

        welcome_text = (
            "🎬 Welcome to YouTube Updater Bot!\n\n"
            "I can help you subscribe to YouTube channels and get notifications "
            "when new videos are uploaded.\n\n"
            "Available commands:\n"
            "/subscribe <YouTube URL> - Subscribe to a channel, video, or playlist\n"
            "/list - Show your subscriptions\n"
            "/unsubscribe - Remove a subscription\n"
            "/help - Show this help message\n\n"
            "Just send me a YouTube URL to get started!"
        )

        await message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        message = update.message
        if message is None:
            logger.warning("Received /help without message context")
            return

        help_text = (
            "🎬 YouTube Updater Bot Commands:\n\n"
            "/start - Start the bot\n"
            "/subscribe <URL> - Subscribe to YouTube channel/video/playlist\n"
            "/list - Show your active subscriptions\n"
            "/unsubscribe - Remove subscriptions\n"
            "/help - Show this help\n\n"
            "You can also just send me a YouTube URL directly!\n\n"
            "Supported URL formats:\n"
            "• Channel: youtube.com/channel/CHANNEL_ID\n"
            "• Channel: youtube.com/@username\n"
            "• Video: youtube.com/watch?v=VIDEO_ID\n"
            "• Playlist: youtube.com/playlist?list=PLAYLIST_ID"
        )

        await message.reply_text(help_text)

    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subscribe command."""
        message = update.message
        if message is None:
            logger.warning("Received /subscribe without message context")
            return

        if not context.args:
            await message.reply_text(
                "Please provide a YouTube URL.\n"
                "Example: /subscribe https://youtube.com/@channelname"
            )
            return

        url = context.args[0]
        await self.handle_youtube_url(update, context, url)

    async def _get_chat_and_user(
        self,
        session: AsyncSession,
        *,
        telegram_user: TelegramUser,
        telegram_chat: TelegramChat,
    ) -> tuple[User | None, DBChat | None]:
        user_repo = UserRepository(session)
        db_user = await user_repo.get_user_by_telegram_id(str(telegram_user.id))
        if db_user is None:
            return None, None
        chat = await self._ensure_chat_record(
            session,
            telegram_chat=telegram_chat,
            db_user_id=db_user.id,
        )
        return db_user, chat

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list command."""
        user = update.effective_user
        message = update.message
        telegram_chat = update.effective_chat
        if user is None or message is None or telegram_chat is None:
            logger.warning("Received /list without required context")
            return

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=message.reply_text,
        ):
            return

        async with AsyncSessionLocal() as session:
            subscription_repo = SubscriptionRepository(session)
            db_user, chat = await self._get_chat_and_user(
                session,
                telegram_user=user,
                telegram_chat=telegram_chat,
            )
            if db_user is None or chat is None:
                await message.reply_text("You don't have any subscriptions yet.")
                return

            subscriptions = await subscription_repo.get_chat_subscriptions(chat.id)
            if not subscriptions:
                await message.reply_text("You don't have any active subscriptions.")
                return

            text = "📋 Your subscriptions:\n\n"
            for sub in subscriptions:
                text += f"• {sub.channel.channel_name}\n"
                text += f"  {sub.channel.channel_url}\n\n"

            await message.reply_text(text)

    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unsubscribe command."""
        user = update.effective_user
        message = update.message
        telegram_chat = update.effective_chat
        if user is None or message is None or telegram_chat is None:
            logger.warning("Received /unsubscribe without required context")
            return

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=message.reply_text,
        ):
            return

        async with AsyncSessionLocal() as session:
            subscription_repo = SubscriptionRepository(session)
            db_user, chat = await self._get_chat_and_user(
                session,
                telegram_user=user,
                telegram_chat=telegram_chat,
            )
            if db_user is None or chat is None:
                await message.reply_text("You don't have any subscriptions to remove.")
                return

            subscriptions = await subscription_repo.get_chat_subscriptions(chat.id)
            if not subscriptions:
                await message.reply_text("You don't have any active subscriptions.")
                return

            keyboard = [
                [
                    InlineKeyboardButton(
                        text=f"❌ {sub.channel.channel_name}",
                        callback_data=f"unsub_{sub.channel.id}",
                    )
                ]
                for sub in subscriptions
            ]
            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await message.reply_text(
                "Select a subscription to remove:", reply_markup=reply_markup
            )

    async def handle_unsubscribe_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle unsubscribe callback queries."""
        query = update.callback_query
        if query is None:
            logger.warning("Received unsubscribe callback without query")
            return

        data = query.data
        if data is None:
            await query.answer("Unable to process your request (missing data).", show_alert=True)
            logger.warning("Callback query missing data")
            await query.edit_message_text("Unable to process your request (missing data).")
            return

        if data == "cancel":
            await query.answer()
            await query.edit_message_text("Cancelled.")
            return

        if not data.startswith("unsub_"):
            await query.answer("Unknown action.", show_alert=True)
            await query.edit_message_text("Unknown action.")
            return

        channel_id = int(data.split("_")[1])
        user = update.effective_user or getattr(query, "from_user", None)
        telegram_chat = update.effective_chat
        if telegram_chat is None and query.message and getattr(query.message, "chat", None):
            telegram_chat = query.message.chat
        if user is None or telegram_chat is None:
            logger.warning("Unsubscribe callback missing user or chat context")
            await query.answer("Unable to identify user or chat for this action.", show_alert=True)
            await query.edit_message_text("Unable to identify user or chat for this action.")
            return

        async def deny(text: str) -> None:
            await query.answer(text, show_alert=True)

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=deny,
        ):
            return

        await query.answer()

        async with AsyncSessionLocal() as session:
            subscription_repo = SubscriptionRepository(session)
            channel_repo = ChannelRepository(session)

            db_user, chat = await self._get_chat_and_user(
                session,
                telegram_user=user,
                telegram_chat=telegram_chat,
            )
            if db_user is None or chat is None:
                await query.edit_message_text("You do not have subscriptions in this chat.")
                return

            channel = await channel_repo.get_channel(channel_id)
            has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                session,
                channel_id,
                exclude_chat_id=chat.id,
            )

            success = await subscription_repo.delete_subscription(chat.id, channel_id)
            if not success:
                await query.edit_message_text("❌ Failed to remove subscription.")
                return

            webhook_success = True
            if not has_other_subscribers and channel is not None:
                await query.edit_message_text(
                    "✅ Removing subscription...\n🔗 Cleaning up notifications..."
                )
                webhook_success = await self.manage_channel_webhook(channel.channel_id, "unsubscribe")

            if webhook_success:
                await query.edit_message_text("✅ Subscription removed successfully!")
            else:
                await query.edit_message_text(
                    "✅ Subscription removed, but failed to clean up notifications."
                )

    async def handle_youtube_url(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str
    ) -> None:
        """Handle YouTube URL processing."""
        user = update.effective_user
        message = update.message or update.effective_message
        telegram_chat = update.effective_chat
        if user is None or message is None or telegram_chat is None:
            logger.warning("handle_youtube_url missing required context")
            return

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=message.reply_text,
        ):
            return

        processing_msg = await message.reply_text("🔍 Processing YouTube URL...")

        try:
            result = await self.youtube_api.resolve_url(url)
            if not result:
                await processing_msg.edit_text(
                    "❌ Could not process this YouTube URL. Please check the URL and try again."
                )
                return

            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                channel_repo = ChannelRepository(session)
                subscription_repo = SubscriptionRepository(session)

                db_user = await user_repo.get_or_create_user(
                    telegram_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                )
                chat = await self._ensure_chat_record(
                    session,
                    telegram_chat=telegram_chat,
                    db_user_id=db_user.id,
                )

                if result.get("type") == "video":
                    channel_info = result["channel"]
                    video_info = result["video"]
                    db_channel = await channel_repo.get_or_create_channel(
                        channel_id=channel_info["id"],
                        channel_name=channel_info["title"],
                        channel_url=channel_info["url"],
                        feed_url=self.youtube_api.get_feed_url(channel_info["id"]),
                    )

                    existing = await subscription_repo.get_subscription(chat.id, db_channel.id)
                    if existing:
                        await processing_msg.edit_text(
                            f"ℹ️ You're already subscribed to **{channel_info['title']}**\n"
                            f"(Found via video: {video_info['title']})",
                            parse_mode="Markdown",
                        )
                        return

                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session, db_channel.id
                    )

                    await subscription_repo.create_subscription(chat.id, db_channel.id)

                    webhook_success = True
                    if not has_other_subscribers:
                        await processing_msg.edit_text(
                            f"✅ Subscribing to **{channel_info['title']}**...\n🔗 Setting up notifications...",
                            parse_mode="Markdown",
                        )
                        webhook_success = await self.manage_channel_webhook(
                            channel_info["id"], "subscribe"
                        )

                    if webhook_success:
                        await processing_msg.edit_text(
                            f"✅ Successfully subscribed to **{channel_info['title']}**!\n"
                            f"(Found via video: {video_info['title']})\n\n"
                            "You'll receive notifications when new videos are uploaded.",
                            parse_mode="Markdown",
                        )
                    else:
                        await processing_msg.edit_text(
                            f"⚠️ Subscribed to **{channel_info['title']}** but couldn't set up real-time notifications.\n"
                            f"(Found via video: {video_info['title']})\n\n"
                            "You may experience delays in notifications.",
                            parse_mode="Markdown",
                        )

                elif result.get("type") == "playlist":
                    await processing_msg.edit_text(
                        "ℹ️ Playlist subscriptions are not yet supported. Please subscribe to the channel instead."
                    )

                else:
                    channel_info = result
                    db_channel = await channel_repo.get_or_create_channel(
                        channel_id=channel_info["id"],
                        channel_name=channel_info["title"],
                        channel_url=channel_info["url"],
                        feed_url=self.youtube_api.get_feed_url(channel_info["id"]),
                    )

                    existing = await subscription_repo.get_subscription(chat.id, db_channel.id)
                    if existing:
                        await processing_msg.edit_text(
                            f"ℹ️ You're already subscribed to **{channel_info['title']}**.",
                            parse_mode="Markdown",
                        )
                        return

                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session, db_channel.id
                    )

                    await subscription_repo.create_subscription(chat.id, db_channel.id)

                    webhook_success = True
                    if not has_other_subscribers:
                        await processing_msg.edit_text(
                            f"✅ Subscribing to **{channel_info['title']}**...\n🔗 Setting up notifications...",
                            parse_mode="Markdown",
                        )
                        webhook_success = await self.manage_channel_webhook(
                            channel_info["id"], "subscribe"
                        )

                    if webhook_success:
                        await processing_msg.edit_text(
                            f"✅ Successfully subscribed to **{channel_info['title']}**!\n\n"
                            "You'll receive notifications when new videos are uploaded.",
                            parse_mode="Markdown",
                        )
                    else:
                        await processing_msg.edit_text(
                            f"⚠️ Subscribed to **{channel_info['title']}** but couldn't set up real-time notifications.\n\n"
                            "You may experience delays in notifications.",
                            parse_mode="Markdown",
                        )

        except Exception as exc:  # pragma: no cover - defensive logging
            logger.error("Error processing YouTube URL: %s", exc)
            await processing_msg.edit_text(
                "❌ An error occurred while processing the URL. Please try again later."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages (looking for YouTube URLs)."""
        message = update.message
        user = update.effective_user
        if message is None or user is None:
            logger.warning("Received message update without required context")
            return

        text = message.text or ""

        youtube_patterns = [
            "youtube.com",
            "youtu.be",
        ]

        if any(pattern in text.lower() for pattern in youtube_patterns) and text:
            words = text.split()
            youtube_url = None

            for word in words:
                if any(pattern in word.lower() for pattern in youtube_patterns):
                    youtube_url = word
                    break

            if youtube_url:
                await self.handle_youtube_url(update, context, youtube_url)
            else:
                await message.reply_text(
                    "I found a YouTube link in your message, but couldn't extract the URL. Please send just the URL."
                )
        else:
            await message.reply_text(
                "Send me a YouTube URL to subscribe to a channel!\n"
                "Or use /help to see available commands."
            )


def setup_handlers(application: Application, youtube_api: YouTubeAPI) -> BotHandlers:
    """Set up bot handlers."""
    handlers = BotHandlers(youtube_api, application.bot)
    logger.info("Setting up bot handlers")

    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("subscribe", handlers.subscribe_command))
    application.add_handler(CommandHandler("list", handlers.list_command))
    application.add_handler(CommandHandler("unsubscribe", handlers.unsubscribe_command))
    application.add_handler(CallbackQueryHandler(handlers.handle_unsubscribe_callback))
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )

    return handlers
