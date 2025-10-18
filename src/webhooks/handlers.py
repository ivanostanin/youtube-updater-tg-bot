import logging
from datetime import datetime

import feedparser
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from ..bot.notifications import NotificationService
from ..database.database import AsyncSessionLocal
from ..database.repository import (
    ChannelRepository,
    NotificationRepository,
    SubscriptionRepository,
    VideoRepository,
)


logger = logging.getLogger(__name__)


class WebhookHandlers:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    async def youtube_webhook(self, request: Request) -> Response:
        """Handle YouTube PubSubHubbub webhook notifications."""
        try:
            # Get the challenge parameter for subscription verification
            challenge = request.query_params.get("hub.challenge")
            if challenge:
                logger.info("YouTube webhook verification received")
                return Response(challenge, media_type="text/plain")

            # Handle the actual notification
            body = await request.body()
            if not body:
                return Response("OK")

            # Parse the Atom feed
            feed = feedparser.parse(body.decode("utf-8"))

            if not feed.entries:
                logger.info("No entries in webhook feed")
                return Response("OK")

            # Process each video entry
            for entry in feed.entries:
                await self.process_video_update(entry)

            return Response("OK")

        except Exception as e:
            logger.error(f"Error processing YouTube webhook: {e}")
            return Response("Error", status_code=500)

    async def process_video_update(self, entry):
        """Process a single video update from the webhook."""
        try:
            # Extract video information
            video_id = entry.get("yt_videoid")
            channel_id = entry.get("yt_channelid")
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")

            if not video_id or not channel_id:
                logger.warning("Missing video_id or channel_id in webhook entry")
                return

            # Parse published date
            published_at = None
            if published:
                try:
                    published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(f"Could not parse published date: {published}")
                    published_at = datetime.utcnow()

            async with AsyncSessionLocal() as session:
                channel_repo = ChannelRepository(session)
                video_repo = VideoRepository(session)
                subscription_repo = SubscriptionRepository(session)
                notification_repo = NotificationRepository(session)

                # Find the channel
                channel = await channel_repo.get_channel_by_id(channel_id)
                if not channel:
                    logger.warning(f"Unknown channel in webhook: {channel_id}")
                    return

                # Check if we already have this video
                existing_video = await video_repo.get_video_by_id(video_id)
                if existing_video:
                    logger.info(f"Video {video_id} already exists, skipping")
                    return

                # Create new video record
                video = await video_repo.create_video(
                    video_id=video_id,
                    channel_id=channel.id,
                    title=title,
                    description=entry.get("summary", ""),
                    url=link,
                    published_at=published_at or datetime.utcnow(),
                    thumbnail_url=None,
                )

                # Get all subscribers for this channel
                subscriptions = await subscription_repo.get_channel_subscribers(channel.id)

                logger.info(
                    f"New video '{title}' from {channel.channel_name}, notifying {len(subscriptions)} subscribers"
                )

                # Send notifications to all subscribers
                for subscription in subscriptions:
                    try:
                        # Send notification via Telegram
                        message_id = await self.notification_service.send_video_notification(
                            user_telegram_id=subscription.user.telegram_id,
                            video=video,
                            channel=channel,
                        )

                        # Record the notification
                        await notification_repo.create_notification(
                            user_id=subscription.user_id,
                            video_id=video.id,
                            message_id=str(message_id) if message_id else None,
                        )

                    except Exception as e:
                        logger.error(
                            f"Error sending notification to user {subscription.user.telegram_id}: {e}"
                        )

        except Exception as e:
            logger.error(f"Error processing video update: {e}")

    async def health_check(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


def create_webhook_app(notification_service: NotificationService) -> Starlette:
    """Create Starlette app for webhook handling."""
    handlers = WebhookHandlers(notification_service)

    app = Starlette()

    # Add routes
    app.add_route("/webhook/youtube", handlers.youtube_webhook, methods=["GET", "POST"])
    app.add_route("/health", handlers.health_check, methods=["GET"])

    return app
