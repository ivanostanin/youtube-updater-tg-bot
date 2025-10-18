from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Notification, Subscription, User, Video, YouTubeChannel


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(
        self, telegram_id: str, username: str = None, first_name: str = None, last_name: str = None
    ) -> User:
        """Get existing user or create new one."""
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if not user:
            user = User(
                telegram_id=telegram_id,
                username=username,
                first_name=first_name,
                last_name=last_name,
            )
            self.session.add(user)
            await self.session.commit()
            await self.session.refresh(user)

        return user

    async def get_user_by_telegram_id(self, telegram_id: str) -> User | None:
        """Get user by Telegram ID."""
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        return result.scalar_one_or_none()


class ChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_channel(
        self, channel_id: str, channel_name: str, channel_url: str, feed_url: str = None
    ) -> YouTubeChannel:
        """Get existing channel or create new one."""
        result = await self.session.execute(
            select(YouTubeChannel).where(YouTubeChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if not channel:
            channel = YouTubeChannel(
                channel_id=channel_id,
                channel_name=channel_name,
                channel_url=channel_url,
                feed_url=feed_url,
            )
            self.session.add(channel)
            await self.session.commit()
            await self.session.refresh(channel)

        return channel

    async def get_channel(self, id: int) -> YouTubeChannel | None:
        """Get channel by database ID."""
        result = await self.session.execute(select(YouTubeChannel).where(YouTubeChannel.id == id))
        return result.scalar_one_or_none()

    async def get_channel_by_id(self, channel_id: str) -> YouTubeChannel | None:
        """Get channel by YouTube channel ID."""
        result = await self.session.execute(
            select(YouTubeChannel).where(YouTubeChannel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active_channels(self) -> list[YouTubeChannel]:
        """Get all active channels."""
        result = await self.session.execute(
            select(YouTubeChannel).where(YouTubeChannel.is_active == True)
        )
        return result.scalars().all()


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_subscription(self, user_id: int, channel_id: int) -> Subscription:
        """Create new subscription."""
        subscription = Subscription(user_id=user_id, channel_id=channel_id)
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        return subscription

    async def get_user_subscriptions(self, user_id: int) -> list[Subscription]:
        """Get all subscriptions for a user."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.is_active == True)
            .options(selectinload(Subscription.channel))
        )
        return result.scalars().all()

    async def get_subscription(self, user_id: int, channel_id: int) -> Subscription | None:
        """Get specific subscription."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .where(Subscription.channel_id == channel_id)
            .where(Subscription.is_active == True)
        )
        return result.scalar_one_or_none()

    async def delete_subscription(self, user_id: int, channel_id: int) -> bool:
        """Delete subscription (soft delete)."""
        subscription = await self.get_subscription(user_id, channel_id)
        if subscription:
            subscription.is_active = False
            await self.session.commit()
            return True
        return False

    async def get_channel_subscribers(self, channel_id: int) -> list[Subscription]:
        """Get all subscribers for a channel."""
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.channel_id == channel_id)
            .where(Subscription.is_active == True)
            .where(Subscription.notification_enabled == True)
            .options(selectinload(Subscription.user))
        )
        return result.scalars().all()


class VideoRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_video(
        self,
        video_id: str,
        channel_id: int,
        title: str,
        description: str,
        url: str,
        published_at: datetime,
        thumbnail_url: str = None,
    ) -> Video:
        """Create new video."""
        video = Video(
            video_id=video_id,
            channel_id=channel_id,
            title=title,
            description=description,
            url=url,
            published_at=published_at,
            thumbnail_url=thumbnail_url,
        )
        self.session.add(video)
        await self.session.commit()
        await self.session.refresh(video)
        return video

    async def get_video_by_id(self, video_id: str) -> Video | None:
        """Get video by YouTube video ID."""
        result = await self.session.execute(select(Video).where(Video.video_id == video_id))
        return result.scalar_one_or_none()

    async def get_channel_videos(self, channel_id: int, limit: int = 10) -> list[Video]:
        """Get recent videos for a channel."""
        result = await self.session.execute(
            select(Video)
            .where(Video.channel_id == channel_id)
            .order_by(Video.published_at.desc())
            .limit(limit)
        )
        return result.scalars().all()


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_notification(
        self, user_id: int, video_id: int, message_id: str = None
    ) -> Notification:
        """Create new notification record."""
        notification = Notification(
            user_id=user_id,
            video_id=video_id,
            message_id=message_id,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def get_user_notifications(self, user_id: int, limit: int = 10) -> list[Notification]:
        """Get recent notifications for a user."""
        result = await self.session.execute(
            select(Notification)
            .where(Notification.user_id == user_id)
            .options(selectinload(Notification.video))
            .order_by(Notification.sent_at.desc())
            .limit(limit)
        )
        return result.scalars().all()
