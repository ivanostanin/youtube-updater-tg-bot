import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from ..database.database import AsyncSessionLocal
from ..database.repository import ChannelRepository, SubscriptionRepository, UserRepository
from ..utils.config import settings
from ..webhooks.pubsub import PubSubManager
from ..youtube.api import YouTubeAPI


logger = logging.getLogger(__name__)


class BotHandlers:
    def __init__(self, youtube_api: YouTubeAPI):
        self.youtube_api = youtube_api
        self.webhook_manager = PubSubManager(webhook_url=settings.webhook_callback_url)

    async def manage_channel_webhook(self, channel_id: str, action: str = "subscribe") -> bool:
        """Manage webhook subscription for a YouTube channel."""
        try:
            logger.info(f"manage_channel_webhook: {action}; channel_id: {channel_id}")
            if action == "subscribe":
                success = await self.webhook_manager.subscribe_to_channel(channel_id)
                if success:
                    logger.info(f"Successfully registered webhook for channel {channel_id}")
                else:
                    logger.error(f"Failed to register webhook for channel {channel_id}")
                return success
            elif action == "unsubscribe":
                success = await self.webhook_manager.unsubscribe_from_channel(channel_id)
                if success:
                    logger.info(f"Successfully unregistered webhook for channel {channel_id}")
                else:
                    logger.error(f"Failed to unregister webhook for channel {channel_id}")
                return success
        except Exception as e:
            logger.error(f"Error managing webhook for channel {channel_id}: {e}")
            return False

    async def check_if_channel_has_other_subscribers(
        self, session, channel_id: int, exclude_user_id: int = None
    ) -> bool:
        """Check if a channel has other active subscribers."""
        subscription_repo = SubscriptionRepository(session)
        subscriptions = await subscription_repo.get_channel_subscribers(channel_id)

        # Filter out the excluded user (if any)
        active_subs = [
            sub
            for sub in subscriptions
            if exclude_user_id is None or sub.user_id != exclude_user_id
        ]

        return len(active_subs) > 0

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        # chat = update.effective_chat
        logger.info(f"Start command received from user {user.id} ({user.username})")

        # Create or get user from database
        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            await user_repo.get_or_create_user(
                telegram_id=str(user.id),
                username=user.username,
                first_name=user.first_name,
                last_name=user.last_name,
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

        await update.message.reply_text(welcome_text)

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
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

        await update.message.reply_text(help_text)

    async def subscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /subscribe command."""
        if not context.args:
            await update.message.reply_text(
                "Please provide a YouTube URL.\n"
                "Example: /subscribe https://youtube.com/@channelname"
            )
            return

        url = context.args[0]
        await self.handle_youtube_url(update, context, url)

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command."""
        user = update.effective_user

        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            subscription_repo = SubscriptionRepository(session)

            db_user = await user_repo.get_user_by_telegram_id(str(user.id))
            if not db_user:
                await update.message.reply_text("You don't have any subscriptions yet.")
                return

            subscriptions = await subscription_repo.get_user_subscriptions(db_user.id)

            if not subscriptions:
                await update.message.reply_text("You don't have any active subscriptions.")
                return

            text = "📋 Your subscriptions:\n\n"
            for sub in subscriptions:
                text += f"• {sub.channel.channel_name}\n"
                text += f"  {sub.channel.channel_url}\n\n"

            await update.message.reply_text(text)

    async def unsubscribe_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /unsubscribe command."""
        user = update.effective_user

        async with AsyncSessionLocal() as session:
            user_repo = UserRepository(session)
            subscription_repo = SubscriptionRepository(session)

            db_user = await user_repo.get_user_by_telegram_id(str(user.id))
            if not db_user:
                await update.message.reply_text("You don't have any subscriptions to remove.")
                return

            subscriptions = await subscription_repo.get_user_subscriptions(db_user.id)

            if not subscriptions:
                await update.message.reply_text("You don't have any active subscriptions.")
                return

            # Create inline keyboard with subscription options
            keyboard = []
            for sub in subscriptions:
                keyboard.append(
                    [
                        InlineKeyboardButton(
                            text=f"❌ {sub.channel.channel_name}",
                            callback_data=f"unsub_{sub.channel.id}",
                        )
                    ]
                )

            keyboard.append([InlineKeyboardButton("Cancel", callback_data="cancel")])

            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text(
                "Select a subscription to remove:", reply_markup=reply_markup
            )

    async def handle_unsubscribe_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle unsubscribe callback queries."""
        query = update.callback_query
        await query.answer()

        if query.data == "cancel":
            await query.edit_message_text("Cancelled.")
            return

        if query.data.startswith("unsub_"):
            channel_id = int(query.data.split("_")[1])
            user = update.effective_user

            async with AsyncSessionLocal() as session:
                user_repo = UserRepository(session)
                subscription_repo = SubscriptionRepository(session)
                channel_repo = ChannelRepository(session)

                db_user = await user_repo.get_user_by_telegram_id(str(user.id))
                if db_user:
                    # Get channel info before deletion for webhook cleanup
                    channel = await channel_repo.get_channel(channel_id)

                    # Check if this user is the last subscriber before deletion
                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session, channel_id, exclude_user_id=db_user.id
                    )

                    success = await subscription_repo.delete_subscription(db_user.id, channel_id)
                    if success:
                        # If this was the last subscriber, unregister the webhook
                        webhook_success = True
                        if not has_other_subscribers and channel:
                            await query.edit_message_text(
                                "✅ Removing subscription...\n🔗 Cleaning up notifications..."
                            )
                            webhook_success = await self.manage_channel_webhook(
                                channel.channel_id, "unsubscribe"
                            )

                        if webhook_success:
                            await query.edit_message_text("✅ Subscription removed successfully!")
                        else:
                            await query.edit_message_text(
                                "✅ Subscription removed, but failed to clean up notifications."
                            )
                    else:
                        await query.edit_message_text("❌ Failed to remove subscription.")

    async def handle_youtube_url(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE, url: str
    ):
        """Handle YouTube URL processing."""
        user = update.effective_user

        # Send processing message
        processing_msg = await update.message.reply_text("🔍 Processing YouTube URL...")

        try:
            # Resolve the URL
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

                # Get or create user
                db_user = await user_repo.get_or_create_user(
                    telegram_id=str(user.id),
                    username=user.username,
                    first_name=user.first_name,
                    last_name=user.last_name,
                )

                # Handle different result types
                if result.get("type") == "video":
                    # Subscribe to the channel of the video
                    channel_info = result["channel"]
                    video_info = result["video"]

                    # Get or create channel
                    db_channel = await channel_repo.get_or_create_channel(
                        channel_id=channel_info["id"],
                        channel_name=channel_info["title"],
                        channel_url=channel_info["url"],
                        feed_url=self.youtube_api.get_feed_url(channel_info["id"]),
                    )

                    # Check if already subscribed
                    existing = await subscription_repo.get_subscription(db_user.id, db_channel.id)
                    if existing:
                        await processing_msg.edit_text(
                            f"ℹ️ You're already subscribed to **{channel_info['title']}**\n"
                            f"(Found via video: {video_info['title']})",
                            parse_mode="Markdown",
                        )
                        return

                    # Check if this is the first subscriber for the channel
                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session, db_channel.id
                    )

                    # Create subscription
                    await subscription_repo.create_subscription(db_user.id, db_channel.id)

                    # Register webhook if this is the first subscriber
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
                            f"You'll receive notifications when new videos are uploaded.",
                            parse_mode="Markdown",
                        )
                    else:
                        await processing_msg.edit_text(
                            f"⚠️ Subscribed to **{channel_info['title']}** but couldn't set up real-time notifications.\n"
                            f"(Found via video: {video_info['title']})\n\n"
                            f"You may experience delays in notifications.",
                            parse_mode="Markdown",
                        )

                elif result.get("type") == "playlist":
                    await processing_msg.edit_text(
                        "ℹ️ Playlist subscriptions are not yet supported. Please subscribe to the channel instead."
                    )

                else:
                    # Direct channel subscription
                    channel_info = result

                    # Get or create channel
                    db_channel = await channel_repo.get_or_create_channel(
                        channel_id=channel_info["id"],
                        channel_name=channel_info["title"],
                        channel_url=channel_info["url"],
                        feed_url=self.youtube_api.get_feed_url(channel_info["id"]),
                    )

                    # Check if already subscribed
                    existing = await subscription_repo.get_subscription(db_user.id, db_channel.id)
                    if existing:
                        await processing_msg.edit_text(
                            f"ℹ️ You're already subscribed to **{channel_info['title']}**",
                            parse_mode="Markdown",
                        )
                        return

                    # Check if this is the first subscriber for the channel
                    has_other_subscribers = await self.check_if_channel_has_other_subscribers(
                        session, db_channel.id
                    )

                    # Create subscription
                    await subscription_repo.create_subscription(db_user.id, db_channel.id)

                    # Register webhook if this is the first subscriber
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
                            f"You'll receive notifications when new videos are uploaded.",
                            parse_mode="Markdown",
                        )
                    else:
                        await processing_msg.edit_text(
                            f"⚠️ Subscribed to **{channel_info['title']}** but couldn't set up real-time notifications.\n\n"
                            f"You may experience delays in notifications.",
                            parse_mode="Markdown",
                        )

        except Exception as e:
            logger.error(f"Error processing YouTube URL: {e}")
            await processing_msg.edit_text(
                "❌ An error occurred while processing the URL. Please try again later."
            )

    async def handle_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages (looking for YouTube URLs)."""
        text = update.message.text
        user = update.effective_user

        logger.info(f"Message received from user {user.id} ({user.username})")
        logger.debug(f"Message content: {text}")

        # Check if message contains YouTube URL
        youtube_patterns = [
            "youtube.com",
            "youtu.be",
        ]

        if any(pattern in text.lower() for pattern in youtube_patterns):
            # Extract URL from the text
            words = text.split()
            youtube_url = None

            for word in words:
                if any(pattern in word.lower() for pattern in youtube_patterns):
                    youtube_url = word
                    break

            if youtube_url:
                await self.handle_youtube_url(update, context, youtube_url)
            else:
                await update.message.reply_text(
                    "I found a YouTube link in your message, but couldn't extract the URL. Please send just the URL."
                )
        else:
            await update.message.reply_text(
                "Send me a YouTube URL to subscribe to a channel!\n"
                "Or use /help to see available commands."
            )


def setup_handlers(application, youtube_api: YouTubeAPI):
    """Set up bot handlers."""
    handlers = BotHandlers(youtube_api)
    logger.info("Setting up bot handlers")

    # Command handlers
    application.add_handler(CommandHandler("start", handlers.start_command))
    application.add_handler(CommandHandler("help", handlers.help_command))
    application.add_handler(CommandHandler("subscribe", handlers.subscribe_command))
    application.add_handler(CommandHandler("list", handlers.list_command))
    application.add_handler(CommandHandler("unsubscribe", handlers.unsubscribe_command))

    # Callback query handler
    application.add_handler(CallbackQueryHandler(handlers.handle_unsubscribe_callback))

    # Message handler for YouTube URLs
    application.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handlers.handle_message)
    )

    return handlers
