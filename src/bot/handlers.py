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
from ..database.models import Subscription, User
from ..database.repository import (
    ChannelRepository,
    ChatRepository,
    SubscriptionRepository,
    UserRepository,
)
from ..services import ACLService
from ..utils.config import settings
from ..utils.logging import get_logger, log_context, new_request_id, sanitize_label
from ..webhooks.pubsub import PubSubManager
from ..youtube.api import YouTubeAPI


logger = get_logger(__name__)


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

    @staticmethod
    def _chat_display_name(chat: TelegramChat | None) -> str | None:
        """Return sanitized chat title for meta logging."""
        if chat is None:
            return None
        for attr in ("title", "username", "full_name", "first_name"):
            value = getattr(chat, attr, None)
            if value:
                return sanitize_label(str(value))
        return None

    @staticmethod
    def _user_display_name(user: TelegramUser | None) -> str | None:
        """Return sanitized user label for meta logging."""
        if user is None:
            return None
        for attr in ("full_name", "username", "first_name", "last_name"):
            value = getattr(user, attr, None)
            if value:
                return sanitize_label(str(value))
        return None

    def _log(
        self,
        level: int,
        message: str,
        *,
        request_id: str,
        operation: str,
        chat: TelegramChat | None = None,
        user: TelegramUser | None = None,
        channel_id: str | None = None,
        subscription_id: int | None = None,
        video_id: str | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        chat_id = getattr(chat, "id", None)
        chat_type = getattr(chat, "type", None)
        user_id = getattr(user, "id", None)
        meta = dict(extra or {})
        chat_label = self._chat_display_name(chat)
        if chat_label:
            meta.setdefault("meta_chat_title", chat_label)
        user_label = self._user_display_name(user)
        if user_label:
            meta.setdefault("meta_user_name", user_label)

        logger.log(
            level,
            message,
            extra=log_context(
                chat_id=str(chat_id) if chat_id is not None else None,
                chat_type=chat_type,
                user_id=str(user_id) if user_id is not None else None,
                channel_id=channel_id,
                subscription_id=subscription_id,
                video_id=video_id,
                operation=operation,
                request_id=request_id,
                **meta,
            ),
        )

    def _debug(self, message: str, **kwargs: Any) -> None:
        self._log(logging.DEBUG, message, **kwargs)

    def _info(self, message: str, **kwargs: Any) -> None:
        self._log(logging.INFO, message, **kwargs)

    def _warning(self, message: str, **kwargs: Any) -> None:
        self._log(logging.WARNING, message, **kwargs)

    def _error(self, message: str, **kwargs: Any) -> None:
        self._log(logging.ERROR, message, **kwargs)

    async def manage_channel_webhook(
        self, channel_id: str, action: str = "subscribe", *, request_id: str | None = None
    ) -> bool:
        """Manage webhook subscription for a YouTube channel."""
        correlation_id = request_id or new_request_id()
        operation = f"webhook.{action}"
        self._debug(
            "Managing channel webhook",
            request_id=correlation_id,
            operation=operation,
            channel_id=channel_id,
        )
        try:
            if action == "subscribe":
                success = await self.webhook_manager.subscribe_to_channel(channel_id)
            elif action == "unsubscribe":
                success = await self.webhook_manager.unsubscribe_from_channel(channel_id)
            else:
                self._warning(
                    "Unknown webhook action requested",
                    request_id=correlation_id,
                    operation=operation,
                    channel_id=channel_id,
                )
                return False

            if success:
                self._info(
                    "Webhook action succeeded",
                    request_id=correlation_id,
                    operation=operation,
                    channel_id=channel_id,
                )
            else:
                self._error(
                    "Webhook action failed",
                    request_id=correlation_id,
                    operation=operation,
                    channel_id=channel_id,
                )
            return success
        except Exception as exc:  # pragma: no cover - defensive logging
            self._error(
                f"Error managing webhook: {exc}",
                request_id=correlation_id,
                operation=operation,
                channel_id=channel_id,
            )
            return False

    async def check_if_channel_has_other_subscribers(
        self,
        session: AsyncSession,
        channel_id: int,
        exclude_chat_id: int | None = None,
        *,
        subscribers: list[Subscription] | None = None,
        request_id: str | None = None,
    ) -> bool:
        """Check if a channel has active subscribers other than the provided chat."""
        correlation_id = request_id or new_request_id()
        subscription_repo = SubscriptionRepository(session)
        if subscribers is None:
            subscribers = await subscription_repo.get_channel_subscribers(
                channel_id, request_id=correlation_id
            )
        has_other = any(sub.chat_id != exclude_chat_id for sub in subscribers)
        self._debug(
            "Computed alternate subscriber count",
            request_id=correlation_id,
            operation="subscription.check_other_subscribers",
            channel_id=str(channel_id),
            extra={
                "meta_total_subscribers": len(subscribers),
                "meta_has_other": has_other,
                "meta_excluded_chat_id": exclude_chat_id,
            },
        )
        return has_other

    async def _ensure_chat_record(
        self,
        session: AsyncSession,
        *,
        telegram_chat: TelegramChat,
        db_user_id: int | None,
        request_id: str | None = None,
    ) -> DBChat:
        """Ensure there's a persisted chat entry for the Telegram chat."""
        correlation_id = request_id or new_request_id()
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

        chat = await chat_repo.get_or_create_chat(
            chat_id=str(telegram_chat.id),
            chat_type=chat_type,
            title=chat_title,
            user_id=user_id,
        )
        self._debug(
            "Ensured chat record",
            request_id=correlation_id,
            operation="chat.ensure_record",
            chat=telegram_chat,
            extra={"meta_chat_pk": getattr(chat, "id", None), "meta_chat_type": chat_type},
        )
        return chat

    async def _require_admin(
        self,
        *,
        telegram_chat: TelegramChat | None,
        telegram_user: TelegramUser | None,
        on_denied: Callable[[str], Awaitable[object]],
        request_id: str,
    ) -> bool:
        """Verify admin permissions for shared chat contexts."""
        operation = "acl.require_admin"
        if telegram_chat is None:
            await on_denied("I couldn't identify which chat triggered this command.")
            self._warning(
                "Missing chat context while enforcing admin requirement",
                request_id=request_id,
                operation=operation,
                user=telegram_user,
            )
            return False

        chat_type = getattr(telegram_chat, "type", "private") or "private"
        if not ACLService.is_group_context(chat_type):
            self._debug(
                "Admin requirement bypassed for private chat",
                request_id=request_id,
                operation=operation,
                chat=telegram_chat,
                user=telegram_user,
            )
            return True

        if self.acl_service is None:
            await on_denied(
                "I can't verify admin permissions for this chat right now. Please try again later."
            )
            self._error(
                "ACL service unavailable; denying group command execution",
                request_id=request_id,
                operation=operation,
                chat=telegram_chat,
                user=telegram_user,
            )
            return False

        chat_identifier: Any = getattr(telegram_chat, "id", None)
        if chat_identifier is None:
            await on_denied("I couldn't identify the target chat for this action.")
            self._warning(
                "Admin check aborted: chat id missing",
                request_id=request_id,
                operation=operation,
                chat=telegram_chat,
                user=telegram_user,
            )
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
            self._warning(
                "Admin verification denied",
                request_id=request_id,
                operation=operation,
                chat=telegram_chat,
                user=telegram_user,
                extra={"meta_denial_reason": sanitize_label(text, max_length=60)},
            )
            await on_denied(text)

        self._debug(
            "Verifying admin permissions via ACL service",
            request_id=request_id,
            operation=operation,
            chat=telegram_chat,
            user=telegram_user,
            extra={"meta_target_chat_id": chat_id},
        )

        result = await self.acl_service.require_admin(
            chat_id=chat_id,
            chat_type=chat_type,
            user_id=user_id,
            on_denied=forward_denial,
            request_id=request_id,
        )
        self._debug(
            "ACL verification completed",
            request_id=request_id,
            operation=operation,
            chat=telegram_chat,
            user=telegram_user,
            extra={"meta_acl_result": result},
        )
        return result

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /start command."""
        request_id = new_request_id()
        user = update.effective_user
        message = update.message
        if user is None or message is None:
            self._warning(
                "Received /start without required user or message context",
                request_id=request_id,
                operation="handler.start",
                chat=update.effective_chat,
                user=user,
            )
            return
        self._debug(
            "Handling /start command",
            request_id=request_id,
            operation="handler.start",
            chat=update.effective_chat,
            user=user,
        )

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
                    request_id=request_id,
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
        self._debug(
            "Completed /start command",
            request_id=request_id,
            operation="handler.start",
            chat=update.effective_chat,
            user=user,
        )

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /help command."""
        request_id = new_request_id()
        message = update.message
        if message is None:
            self._warning(
                "Received /help without message context",
                request_id=request_id,
                operation="handler.help",
                chat=update.effective_chat,
                user=update.effective_user,
            )
            return
        self._debug(
            "Handling /help command",
            request_id=request_id,
            operation="handler.help",
            chat=update.effective_chat,
            user=update.effective_user,
        )

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
        self._debug(
            "Completed /help command",
            request_id=request_id,
            operation="handler.help",
            chat=update.effective_chat,
            user=update.effective_user,
        )

    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /subscribe command."""
        request_id = new_request_id()
        message = update.message
        if message is None:
            self._warning(
                "Received /subscribe without message context",
                request_id=request_id,
                operation="handler.subscribe",
                chat=update.effective_chat,
                user=update.effective_user,
            )
            return

        if not context.args:
            await message.reply_text(
                "Please provide a YouTube URL.\n"
                "Example: /subscribe https://youtube.com/@channelname"
            )
            self._debug(
                "Subscribe command missing URL argument",
                request_id=request_id,
                operation="handler.subscribe",
                chat=update.effective_chat,
                user=update.effective_user,
            )
            return

        url = context.args[0]
        self._debug(
            "Dispatching YouTube URL from /subscribe",
            request_id=request_id,
            operation="handler.subscribe",
            chat=update.effective_chat,
            user=update.effective_user,
            extra={"meta_url_preview": sanitize_label(url)},
        )
        await self.handle_youtube_url(update, context, url, request_id=request_id)
        self._debug(
            "Finished /subscribe command",
            request_id=request_id,
            operation="handler.subscribe",
            chat=update.effective_chat,
            user=update.effective_user,
        )

    async def _get_chat_and_user(
        self,
        session: AsyncSession,
        *,
        telegram_user: TelegramUser,
        telegram_chat: TelegramChat,
        request_id: str,
    ) -> tuple[User | None, DBChat | None]:
        """Ensure both the acting user and chat exist in the database."""
        user_repo = UserRepository(session)
        db_user = await user_repo.get_or_create_user(
            telegram_id=str(telegram_user.id),
            username=getattr(telegram_user, "username", None),
            first_name=getattr(telegram_user, "first_name", None),
            last_name=getattr(telegram_user, "last_name", None),
        )
        chat = await self._ensure_chat_record(
            session,
            telegram_chat=telegram_chat,
            db_user_id=db_user.id if db_user else None,
            request_id=request_id,
        )
        self._debug(
            "Ensured chat and user records",
            request_id=request_id,
            operation="chat.ensure_user_link",
            chat=telegram_chat,
            user=telegram_user,
            extra={"meta_user_pk": getattr(db_user, "id", None), "meta_chat_pk": getattr(chat, "id", None)},
        )
        return db_user, chat

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /list command."""
        request_id = new_request_id()
        user = update.effective_user
        message = update.message
        telegram_chat = update.effective_chat
        if user is None or message is None or telegram_chat is None:
            self._warning(
                "Received /list without required context",
                request_id=request_id,
                operation="handler.list",
                chat=telegram_chat,
                user=user,
            )
            return

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=message.reply_text,
            request_id=request_id,
        ):
            return
        self._debug(
            "Listing subscriptions",
            request_id=request_id,
            operation="handler.list",
            chat=telegram_chat,
            user=user,
        )

        async with AsyncSessionLocal() as session:
            subscription_repo = SubscriptionRepository(session)
            _db_user, chat = await self._get_chat_and_user(
                session,
                telegram_user=user,
                telegram_chat=telegram_chat,
                request_id=request_id,
            )
            if chat is None:
                await message.reply_text("You don't have any subscriptions yet.")
                self._debug(
                    "List command found no chat record",
                    request_id=request_id,
                    operation="handler.list",
                    chat=telegram_chat,
                    user=user,
                )
                return

            subscriptions = await subscription_repo.get_chat_subscriptions(
                chat.id, request_id=request_id
            )

        if not subscriptions:
            await message.reply_text("You don't have any active subscriptions.")
            self._debug(
                "List command found zero subscriptions",
                request_id=request_id,
                operation="handler.list",
                chat=telegram_chat,
                user=user,
            )
            return

        text = "📋 Your subscriptions:\n\n"
        for sub in subscriptions:
            text += f"• {sub.channel.channel_name}\n"
            text += f"  {sub.channel.channel_url}\n\n"

        await message.reply_text(text)
        self._debug(
            "List command completed",
            request_id=request_id,
            operation="handler.list",
            chat=telegram_chat,
            user=user,
            extra={"meta_subscription_count": len(subscriptions)},
        )

    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle /unsubscribe command."""
        request_id = new_request_id()
        user = update.effective_user
        message = update.message
        telegram_chat = update.effective_chat
        if user is None or message is None or telegram_chat is None:
            self._warning(
                "Received /unsubscribe without required context",
                request_id=request_id,
                operation="handler.unsubscribe",
                chat=telegram_chat,
                user=user,
            )
            return

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=message.reply_text,
            request_id=request_id,
        ):
            return
        self._debug(
            "Preparing unsubscribe options",
            request_id=request_id,
            operation="handler.unsubscribe",
            chat=telegram_chat,
            user=user,
        )

        async with AsyncSessionLocal() as session:
            subscription_repo = SubscriptionRepository(session)
            _db_user, chat = await self._get_chat_and_user(
                session,
                telegram_user=user,
                telegram_chat=telegram_chat,
                request_id=request_id,
            )
            if chat is None:
                await message.reply_text("You don't have any subscriptions to remove.")
                self._debug(
                    "Unsubscribe command has no chat binding",
                    request_id=request_id,
                    operation="handler.unsubscribe",
                    chat=telegram_chat,
                    user=user,
                )
                return

            subscriptions = await subscription_repo.get_chat_subscriptions(
                chat.id, request_id=request_id
            )

        if not subscriptions:
            await message.reply_text("You don't have any active subscriptions.")
            self._debug(
                "Unsubscribe command found zero subscriptions",
                request_id=request_id,
                operation="handler.unsubscribe",
                chat=telegram_chat,
                user=user,
            )
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
        await message.reply_text("Select a subscription to remove:", reply_markup=reply_markup)
        self._debug(
            "Rendered unsubscribe keyboard",
            request_id=request_id,
            operation="handler.unsubscribe",
            chat=telegram_chat,
            user=user,
            extra={"meta_subscription_count": len(subscriptions)},
        )

    async def handle_unsubscribe_callback(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle unsubscribe callback queries."""
        request_id = new_request_id()
        operation = "handler.unsubscribe.callback"
        query = update.callback_query
        if query is None:
            self._warning(
                "Received unsubscribe callback without query payload",
                request_id=request_id,
                operation=operation,
                chat=update.effective_chat,
                user=update.effective_user,
            )
            return

        data = query.data
        if data is None:
            await query.answer("Unable to process your request (missing data).", show_alert=True)
            await query.edit_message_text("Unable to process your request (missing data).")
            self._warning(
                "Callback query missing data",
                request_id=request_id,
                operation=operation,
                chat=update.effective_chat,
                user=update.effective_user,
            )
            return

        if data == "cancel":
            await query.answer()
            await query.edit_message_text("Cancelled.")
            self._debug(
                "User cancelled unsubscribe flow",
                request_id=request_id,
                operation=operation,
                chat=update.effective_chat,
                user=update.effective_user,
            )
            return

        if not data.startswith("unsub_"):
            await query.answer("Unknown action.", show_alert=True)
            await query.edit_message_text("Unknown action.")
            self._warning(
                "Unknown unsubscribe callback action",
                request_id=request_id,
                operation=operation,
                chat=update.effective_chat,
                user=update.effective_user,
                extra={"meta_callback_data": sanitize_label(data)},
            )
            return

        try:
            channel_id = int(data.split("_")[1])
        except (IndexError, ValueError):
            await query.answer("Unable to parse subscription identifier.", show_alert=True)
            await query.edit_message_text("Unable to parse subscription identifier.")
            self._warning(
                "Failed to parse channel id from callback",
                request_id=request_id,
                operation=operation,
                chat=update.effective_chat,
                user=update.effective_user,
                extra={"meta_callback_data": sanitize_label(data)},
            )
            return

        user = update.effective_user or getattr(query, "from_user", None)
        telegram_chat = update.effective_chat
        if telegram_chat is None and query.message and getattr(query.message, "chat", None):
            telegram_chat = query.message.chat
        if user is None or telegram_chat is None:
            await query.answer("Unable to identify user or chat for this action.", show_alert=True)
            await query.edit_message_text("Unable to identify user or chat for this action.")
            self._warning(
                "Unsubscribe callback missing user or chat context",
                request_id=request_id,
                operation=operation,
                chat=telegram_chat,
                user=user,
                channel_id=str(channel_id),
            )
            return

        async def deny(text: str) -> None:
            await query.answer(text, show_alert=True)

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=deny,
            request_id=request_id,
        ):
            return

        await query.answer()

        async with AsyncSessionLocal() as session:
            subscription_repo = SubscriptionRepository(session)
            channel_repo = ChannelRepository(session)

            _db_user, chat = await self._get_chat_and_user(
                session,
                telegram_user=user,
                telegram_chat=telegram_chat,
                request_id=request_id,
            )
            if chat is None:
                await query.edit_message_text("You do not have subscriptions in this chat.")
                self._debug(
                    "Unsubscribe callback missing chat binding",
                    request_id=request_id,
                    operation=operation,
                    chat=telegram_chat,
                    user=user,
                    channel_id=str(channel_id),
                )
                return

            channel = await channel_repo.get_channel(channel_id)
            subscription = await subscription_repo.get_subscription(
                chat.id, channel_id, request_id=request_id
            )
            has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                session,
                channel_id,
                exclude_chat_id=chat.id,
                request_id=request_id,
            )
            self._debug(
                "Evaluated unsubscribe target",
                request_id=request_id,
                operation=operation,
                chat=telegram_chat,
                user=user,
                channel_id=str(channel_id),
                subscription_id=getattr(subscription, "id", None),
                extra={
                    "meta_has_other_subscribers": has_other_subscribers,
                    "meta_channel_title": sanitize_label(
                        getattr(channel, "channel_name", None)
                    ),
                },
            )

            success = await subscription_repo.delete_subscription(
                chat.id, channel_id, request_id=request_id
            )
            if not success:
                await query.edit_message_text("❌ Failed to remove subscription.")
                self._error(
                    "Failed to remove subscription during callback",
                    request_id=request_id,
                    operation=operation,
                    chat=telegram_chat,
                    user=user,
                    channel_id=str(channel_id),
                )
                return

            webhook_success = True
            if not has_other_subscribers and channel is not None:
                await query.edit_message_text(
                    "✅ Removing subscription...\n🔗 Cleaning up notifications..."
                )
                webhook_success = await self.manage_channel_webhook(
                    channel.channel_id, "unsubscribe", request_id=request_id
                )
                if webhook_success and subscription is not None:
                    subscription.webhook_url = None
                    await session.commit()

            if webhook_success:
                await query.edit_message_text("✅ Subscription removed successfully!")
                self._info(
                    "Subscription removed via callback",
                    request_id=request_id,
                    operation=operation,
                    chat=telegram_chat,
                    user=user,
                    channel_id=str(channel_id),
                )
            else:
                await query.edit_message_text(
                    "✅ Subscription removed, but failed to clean up notifications."
                )
                self._warning(
                    "Webhook cleanup failed after unsubscribe",
                    request_id=request_id,
                    operation=operation,
                    chat=telegram_chat,
                    user=user,
                    channel_id=str(channel_id),
                )

    async def handle_youtube_url(
        self,
        update: Update,
        context: ContextTypes.DEFAULT_TYPE,
        url: str,
        request_id: str | None = None,
    ) -> None:
        """Handle YouTube URL processing."""
        correlation_id = request_id or new_request_id()
        operation = "handler.subscribe.url"
        user = update.effective_user
        message = update.message or update.effective_message
        telegram_chat = update.effective_chat
        if user is None or message is None or telegram_chat is None:
            self._warning(
                "handle_youtube_url missing required context",
                request_id=correlation_id,
                operation=operation,
                chat=telegram_chat,
                user=user,
            )
            return

        if not await self._require_admin(
            telegram_chat=telegram_chat,
            telegram_user=user,
            on_denied=message.reply_text,
            request_id=correlation_id,
        ):
            return

        self._debug(
            "Processing YouTube URL",
            request_id=correlation_id,
            operation=operation,
            chat=telegram_chat,
            user=user,
            extra={"meta_url_preview": sanitize_label(url)},
        )

        processing_msg = await message.reply_text("🔍 Processing YouTube URL...")

        try:
            result = await self.youtube_api.resolve_url(url, request_id=correlation_id)
            if not result:
                await processing_msg.edit_text(
                    "❌ Could not process this YouTube URL. Please check the URL and try again."
                )
                self._warning(
                    "Unable to resolve YouTube URL",
                    request_id=correlation_id,
                    operation=operation,
                    chat=telegram_chat,
                    user=user,
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
                     request_id=correlation_id,
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

                    existing = await subscription_repo.get_subscription(
                        chat.id, db_channel.id, request_id=correlation_id
                    )
                    if existing:
                        await processing_msg.edit_text(
                            f"ℹ️ You're already subscribed to **{channel_info['title']}**\n"
                            f"(Found via video: {video_info['title']})",
                            parse_mode="Markdown",
                        )
                        self._debug(
                            "Subscription already exists for video URL",
                            request_id=correlation_id,
                            operation=operation,
                            chat=telegram_chat,
                            user=user,
                            channel_id=channel_info["id"],
                            subscription_id=existing.id,
                        )
                        return

                    channel_subscribers = await subscription_repo.get_channel_subscribers(
                        db_channel.id, request_id=correlation_id
                    )
                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session,
                        db_channel.id,
                        exclude_chat_id=chat.id,
                        subscribers=channel_subscribers,
                        request_id=correlation_id,
                    )

                    subscription = await subscription_repo.create_subscription(
                        chat.id, db_channel.id, request_id=correlation_id
                    )

                    webhook_success = True
                    if not has_other_subscribers:
                        await processing_msg.edit_text(
                            f"✅ Subscribing to **{channel_info['title']}**...\n🔗 Setting up notifications...",
                            parse_mode="Markdown",
                        )
                        webhook_success = await self.manage_channel_webhook(
                            channel_info["id"], "subscribe", request_id=correlation_id
                        )
                        if webhook_success and subscription.webhook_url != settings.webhook_callback_url:
                            subscription.webhook_url = settings.webhook_callback_url
                            await session.commit()
                    else:
                        inherited_webhook = next(
                            (
                                sub.webhook_url
                                for sub in channel_subscribers
                                if sub.chat_id != chat.id and sub.webhook_url
                            ),
                            None,
                        )
                        if (
                            inherited_webhook
                            and subscription.webhook_url != inherited_webhook
                            and subscription.webhook_url is None
                        ):
                            subscription.webhook_url = inherited_webhook
                            await session.commit()

                    if webhook_success:
                        await processing_msg.edit_text(
                            f"✅ Successfully subscribed to **{channel_info['title']}**!\n"
                            f"(Found via video: {video_info['title']})\n\n"
                            "You'll receive notifications when new videos are uploaded.",
                            parse_mode="Markdown",
                        )
                        self._info(
                            "Subscription created via video URL",
                            request_id=correlation_id,
                            operation=operation,
                            chat=telegram_chat,
                            user=user,
                            channel_id=channel_info["id"],
                        )
                    else:
                        await processing_msg.edit_text(
                            f"⚠️ Subscribed to **{channel_info['title']}** but couldn't set up real-time notifications.\n"
                            f"(Found via video: {video_info['title']})\n\n"
                            "You may experience delays in notifications.",
                            parse_mode="Markdown",
                        )
                        self._warning(
                            "Subscription created but webhook setup failed",
                            request_id=correlation_id,
                            operation=operation,
                            chat=telegram_chat,
                            user=user,
                            channel_id=channel_info["id"],
                        )

                elif result.get("type") == "playlist":
                    await processing_msg.edit_text(
                        "ℹ️ Playlist subscriptions are not yet supported. Please subscribe to the channel instead."
                    )
                    self._warning(
                        "Playlist subscriptions not supported",
                        request_id=correlation_id,
                        operation=operation,
                        chat=telegram_chat,
                        user=user,
                    )

                else:
                    channel_info = result
                    db_channel = await channel_repo.get_or_create_channel(
                        channel_id=channel_info["id"],
                        channel_name=channel_info["title"],
                        channel_url=channel_info["url"],
                        feed_url=self.youtube_api.get_feed_url(channel_info["id"]),
                    )

                    existing = await subscription_repo.get_subscription(
                        chat.id, db_channel.id, request_id=correlation_id
                    )
                    if existing:
                        await processing_msg.edit_text(
                            f"ℹ️ You're already subscribed to **{channel_info['title']}**.",
                            parse_mode="Markdown",
                        )
                        self._debug(
                            "Subscription already exists for channel URL",
                            request_id=correlation_id,
                            operation=operation,
                            chat=telegram_chat,
                            user=user,
                            channel_id=channel_info["id"],
                            subscription_id=existing.id,
                        )
                        return

                    channel_subscribers = await subscription_repo.get_channel_subscribers(
                        db_channel.id, request_id=correlation_id
                    )
                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session,
                        db_channel.id,
                        exclude_chat_id=chat.id,
                        subscribers=channel_subscribers,
                        request_id=correlation_id,
                    )

                    subscription = await subscription_repo.create_subscription(
                        chat.id, db_channel.id, request_id=correlation_id
                    )

                    webhook_success = True
                    if not has_other_subscribers:
                        await processing_msg.edit_text(
                            f"✅ Subscribing to **{channel_info['title']}**...\n🔗 Setting up notifications...",
                            parse_mode="Markdown",
                        )
                        webhook_success = await self.manage_channel_webhook(
                            channel_info["id"], "subscribe", request_id=correlation_id
                        )
                        if webhook_success and subscription.webhook_url != settings.webhook_callback_url:
                            subscription.webhook_url = settings.webhook_callback_url
                            await session.commit()
                    else:
                        inherited_webhook = next(
                            (
                                sub.webhook_url
                                for sub in channel_subscribers
                                if sub.chat_id != chat.id and sub.webhook_url
                            ),
                            None,
                        )
                        if (
                            inherited_webhook
                            and subscription.webhook_url != inherited_webhook
                            and subscription.webhook_url is None
                        ):
                            subscription.webhook_url = inherited_webhook
                            await session.commit()

                    if webhook_success:
                        await processing_msg.edit_text(
                            f"✅ Successfully subscribed to **{channel_info['title']}**!\n\n"
                            "You'll receive notifications when new videos are uploaded.",
                            parse_mode="Markdown",
                        )
                        self._info(
                            "Subscription created via channel URL",
                            request_id=correlation_id,
                            operation=operation,
                            chat=telegram_chat,
                            user=user,
                            channel_id=channel_info["id"],
                        )
                    else:
                        await processing_msg.edit_text(
                            f"⚠️ Subscribed to **{channel_info['title']}** but couldn't set up real-time notifications.\n\n"
                            "You may experience delays in notifications.",
                            parse_mode="Markdown",
                        )
                        self._warning(
                            "Subscription created but webhook setup failed",
                            request_id=correlation_id,
                            operation=operation,
                            chat=telegram_chat,
                            user=user,
                            channel_id=channel_info["id"],
                        )

        except Exception as exc:  # pragma: no cover - defensive logging
            self._error(
                f"Error processing YouTube URL: {exc}",
                request_id=correlation_id,
                operation=operation,
                chat=telegram_chat,
                user=user,
            )
            await processing_msg.edit_text(
                "❌ An error occurred while processing the URL. Please try again later."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Handle text messages (looking for YouTube URLs)."""
        request_id = new_request_id()
        message = update.message
        user = update.effective_user
        telegram_chat = update.effective_chat
        if message is None or user is None or telegram_chat is None:
            self._warning(
                "Received message update without required context",
                request_id=request_id,
                operation="handler.message",
                chat=telegram_chat,
                user=user,
            )
            return

        text = message.text or ""
        chat_type = getattr(telegram_chat, "type", "private")
        is_private_chat = chat_type == "private"

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
                self._debug(
                    "Detected YouTube URL in message",
                    request_id=request_id,
                    operation="handler.message",
                    chat=telegram_chat,
                    user=user,
                    extra={
                        "meta_message_preview": sanitize_label(text),
                        "meta_url_preview": sanitize_label(youtube_url),
                    },
                )
                await self.handle_youtube_url(
                    update, context, youtube_url, request_id=request_id
                )
            elif is_private_chat:
                await message.reply_text(
                    "I found a YouTube link in your message, but couldn't extract the URL. Please send just the URL."
                )
                self._warning(
                    "Unable to extract URL from text message",
                    request_id=request_id,
                    operation="handler.message",
                    chat=telegram_chat,
                    user=user,
                )
        elif is_private_chat:
            await message.reply_text(
                "Send me a YouTube URL to subscribe to a channel!\n"
                "Or use /help to see available commands."
            )
            self._debug(
                "Prompted user for YouTube URL",
                request_id=request_id,
                operation="handler.message",
                chat=telegram_chat,
                user=user,
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
