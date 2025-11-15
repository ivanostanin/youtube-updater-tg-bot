from datetime import datetime

import feedparser
from feedparser import FeedParserDict
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
from ..utils.config import settings
from ..utils.logging import get_logger, log_context, new_request_id, sanitize_label


logger = get_logger(__name__)


class WebhookHandlers:
    def __init__(self, notification_service: NotificationService):
        self.notification_service = notification_service

    async def youtube_webhook(self, request: Request) -> Response:
        """Handle YouTube PubSubHubbub webhook notifications."""
        request_id = new_request_id()
        operation = "webhook.youtube"
        try:
            # Get the challenge parameter for subscription verification
            challenge = request.query_params.get("hub.challenge")
            if challenge:
                logger.info(
                    "YouTube webhook verification received",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        meta_event="challenge",
                    ),
                )
                return Response(challenge, media_type="text/plain")

            # Handle the actual notification
            body = await request.body()
            if not body:
                logger.debug(
                    "Webhook received empty body",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        meta_event="empty_body",
                    ),
                )
                return Response("OK")

            # Parse the Atom feed
            feed = feedparser.parse(body.decode("utf-8"))

            if not feed.entries:
                logger.info(
                    "Webhook feed contained no entries",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        meta_event="empty_feed",
                    ),
                )
                return Response("OK")

            logger.debug(
                "Processing webhook feed entries",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    meta_entry_count=len(feed.entries),
                ),
            )

            # Process each video entry
            for entry in feed.entries:
                await self.process_video_update(entry, request_id=request_id)

            return Response("OK")

        except Exception as e:
            logger.error(
                "Error processing YouTube webhook",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return Response("Error", status_code=500)

    async def process_video_update(
        self, entry: FeedParserDict, *, request_id: str | None = None
    ) -> None:
        """Process a single video update from the webhook."""
        correlation_id = request_id or new_request_id()
        operation = "webhook.youtube.process_entry"
        try:
            # Extract video information
            video_id = entry.get("yt_videoid")
            channel_id = entry.get("yt_channelid")
            title = entry.get("title", "")
            link = entry.get("link", "")
            published = entry.get("published", "")

            if not video_id or not channel_id:
                logger.warning(
                    "Missing identifiers in webhook entry",
                    extra=log_context(
                        request_id=correlation_id,
                        operation=operation,
                        video_id=video_id,
                        channel_id=channel_id,
                    ),
                )
                return

            # Parse published date
            published_at = None
            if published:
                try:
                    published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
                except ValueError:
                    logger.warning(
                        "Could not parse published date",
                        extra=log_context(
                            request_id=correlation_id,
                            operation=operation,
                            video_id=video_id,
                            channel_id=channel_id,
                            meta_published_raw=published,
                        ),
                    )
                    published_at = datetime.utcnow()

            async with AsyncSessionLocal() as session:
                channel_repo = ChannelRepository(session)
                video_repo = VideoRepository(session)
                subscription_repo = SubscriptionRepository(session)
                notification_repo = NotificationRepository(session)

                # Find the channel
                channel = await channel_repo.get_channel_by_id(channel_id)
                if not channel:
                    logger.warning(
                        "Unknown channel in webhook entry",
                        extra=log_context(
                            request_id=correlation_id,
                            operation=operation,
                            channel_id=channel_id,
                        ),
                    )
                    return

                # Check if we already have this video
                existing_video = await video_repo.get_video_by_id(video_id)
                if existing_video:
                    logger.info(
                        "Video already exists, skipping",
                        extra=log_context(
                            request_id=correlation_id,
                            operation=operation,
                            video_id=video_id,
                            channel_id=channel_id,
                        ),
                    )
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
                subscriptions = await subscription_repo.get_channel_subscribers(
                    channel.id, request_id=correlation_id
                )

                logger.info(
                    "Dispatching video notification to subscribers",
                    extra=log_context(
                        request_id=correlation_id,
                        operation=operation,
                        video_id=video.video_id,
                        channel_id=channel.channel_id,
                        meta_video_title=sanitize_label(title),
                        meta_channel_title=sanitize_label(channel.channel_name),
                        meta_subscriber_count=len(subscriptions),
                    ),
                )

                # Send notifications to all subscribers
                for subscription in subscriptions:
                    try:
                        chat = subscription.chat

                        message_id = await self.notification_service.send_video_notification(
                            chat_telegram_id=chat.chat_id,
                            video=video,
                            channel=channel,
                            chat_title=chat.title,
                            chat_type=chat.chat_type,
                            request_id=correlation_id,
                        )

                        await notification_repo.create_notification(
                            chat_id=chat.id,
                            video_id=video.id,
                            message_id=str(message_id) if message_id else None,
                        )

                    except Exception as e:
                        logger.error(
                            "Error sending notification for subscriber",
                            extra=log_context(
                                request_id=correlation_id,
                                operation=operation,
                                video_id=video.video_id,
                                channel_id=channel.channel_id,
                                subscription_id=subscription.id,
                                chat_id=subscription.chat.chat_id if subscription.chat else None,
                                meta_error=sanitize_label(str(e)),
                            ),
                        )

        except Exception as e:
            logger.error(
                "Error processing video update",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    meta_error=sanitize_label(str(e)),
                ),
            )

    async def health_check(self, request: Request) -> JSONResponse:
        """Health check endpoint."""
        return JSONResponse(
            {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}
        )


def create_webhook_app(notification_service: NotificationService) -> Starlette:
    """Create Starlette app for webhook handling."""
    handlers = WebhookHandlers(notification_service)

    app = Starlette()

    # Add routes
    app.add_route(settings.webhook_path, handlers.youtube_webhook, methods=["GET", "POST"])
    app.add_route("/health", handlers.health_check, methods=["GET"])

    return app
