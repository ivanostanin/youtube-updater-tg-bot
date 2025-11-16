from __future__ import annotations

import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ..utils.locale_codes import SUPPORTED_LOCALES, normalize_locale_code
from ..utils.logging import get_logger, log_context, new_request_id
from .models import Chat, Notification, Subscription, User, Video, YouTubeChannel


logger = get_logger(__name__)


def _repo_log(
    level: int,
    message: str,
    *,
    request_id: str,
    operation: str,
    chat_id: int | str | None = None,
    channel_id: int | str | None = None,
    subscription_id: int | None = None,
    extra: dict[str, object] | None = None,
) -> None:
    payload: dict[str, object] = {
        "request_id": request_id,
        "operation": operation,
        "chat_id": str(chat_id) if chat_id is not None else None,
        "channel_id": str(channel_id) if channel_id is not None else None,
        "subscription_id": subscription_id,
    }
    if extra:
        payload.update(extra)
    logger.log(level, message, extra=log_context(**payload))


class UserRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_user(
        self,
        telegram_id: str,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
    ) -> User:
        """Get existing user or create new one."""
        result = await self.session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one_or_none()

        if user is None:
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


class ChatRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_chat(
        self,
        *,
        chat_id: str,
        chat_type: str,
        title: str | None = None,
        user_id: int | None = None,
        preferred_locale: str | None = None,
    ) -> Chat:
        """Get existing chat or create a new record."""
        result = await self.session.execute(select(Chat).where(Chat.chat_id == chat_id))
        chat = result.scalar_one_or_none()
        normalized_locale = normalize_locale_code(preferred_locale)

        if chat:
            updated = False
            if title and chat.title != title:
                chat.title = title
                updated = True
            if chat.chat_type != chat_type:
                chat.chat_type = chat_type
                updated = True
            if user_id and chat.user_id != user_id:
                chat.user_id = user_id
                updated = True
            if normalized_locale and chat.preferred_locale != normalized_locale:
                chat.preferred_locale = normalized_locale
                updated = True
            if updated:
                await self.session.commit()
            return chat

        chat = Chat(
            chat_id=chat_id,
            chat_type=chat_type,
            title=title,
            user_id=user_id,
            preferred_locale=normalized_locale,
        )
        self.session.add(chat)
        await self.session.commit()
        await self.session.refresh(chat)
        return chat

    async def get_chat(self, chat_pk: int) -> Chat | None:
        result = await self.session.execute(select(Chat).where(Chat.id == chat_pk))
        return result.scalar_one_or_none()

    async def get_chat_by_identifier(self, chat_id: str) -> Chat | None:
        result = await self.session.execute(select(Chat).where(Chat.chat_id == chat_id))
        return result.scalar_one_or_none()

    async def update_chat_locale(self, chat: Chat, preferred_locale: str) -> Chat:
        """Persist a preferred locale for the chat."""
        normalized_locale = normalize_locale_code(preferred_locale)
        if normalized_locale is None:
            allowed = ", ".join(SUPPORTED_LOCALES)
            raise ValueError(f"Unsupported locale: {preferred_locale}. Allowed: {allowed}")
        if chat.preferred_locale == normalized_locale:
            return chat
        chat.preferred_locale = normalized_locale
        await self.session.commit()
        await self.session.refresh(chat)
        return chat


class ChannelRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_or_create_channel(
        self,
        channel_id: str,
        channel_name: str,
        channel_url: str,
        feed_url: str | None = None,
    ) -> YouTubeChannel:
        """Get existing channel or create new one."""
        result = await self.session.execute(
            select(YouTubeChannel).where(YouTubeChannel.channel_id == channel_id)
        )
        channel = result.scalar_one_or_none()

        if channel is None:
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

    async def get_channel(self, pk: int) -> YouTubeChannel | None:
        result = await self.session.execute(select(YouTubeChannel).where(YouTubeChannel.id == pk))
        return result.scalar_one_or_none()

    async def get_channel_by_id(self, channel_id: str) -> YouTubeChannel | None:
        result = await self.session.execute(
            select(YouTubeChannel).where(YouTubeChannel.channel_id == channel_id)
        )
        return result.scalar_one_or_none()

    async def get_all_active_channels(self) -> list[YouTubeChannel]:
        result = await self.session.execute(select(YouTubeChannel).where(YouTubeChannel.is_active))
        return list(result.scalars().all())


class SubscriptionRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def _fetch_subscription_rows(
        self,
        chat_id: int,
        channel_id: int,
        *,
        include_inactive: bool = True,
        limit: int | None = None,
        request_id: str | None = None,
    ) -> list[Subscription]:
        correlation_id = request_id or new_request_id()
        operation = "repository.fetch_subscription_rows"
        _repo_log(
            logging.DEBUG,
            "Fetching subscription rows",
            request_id=correlation_id,
            operation=operation,
            chat_id=chat_id,
            channel_id=channel_id,
            extra={"meta_include_inactive": include_inactive, "meta_limit": limit},
        )
        stmt = (
            select(Subscription)
            .where(Subscription.chat_id == chat_id)
            .where(Subscription.channel_id == channel_id)
            .order_by(Subscription.created_at.desc(), Subscription.id.desc())
        )
        if not include_inactive:
            stmt = stmt.where(Subscription.is_active)
        if limit is not None:
            stmt = stmt.limit(limit)
        result = await self.session.execute(stmt)
        rows = list(result.scalars().all())
        _repo_log(
            logging.DEBUG,
            "Fetched subscription rows",
            request_id=correlation_id,
            operation=operation,
            chat_id=chat_id,
            channel_id=channel_id,
            extra={"meta_row_count": len(rows)},
        )
        return rows

    async def _ensure_single_subscription(
        self,
        subscriptions: list[Subscription],
        *,
        chat_id: int,
        channel_id: int,
        request_id: str | None = None,
    ) -> Subscription | None:
        if not subscriptions:
            return None

        canonical = subscriptions[0]
        if len(subscriptions) == 1:
            return canonical

        duplicates = subscriptions[1:]
        correlation_id = request_id or new_request_id()
        _repo_log(
            logging.WARNING,
            "Removing duplicate subscription rows",
            request_id=correlation_id,
            operation="repository.clean_duplicate_subscriptions",
            chat_id=chat_id,
            channel_id=channel_id,
            extra={"meta_duplicate_count": len(subscriptions)},
        )
        for duplicate in duplicates:
            await self.session.delete(duplicate)

        # Ensure deletions are flushed before other updates to avoid unique constraint violations.
        await self.session.flush()
        return canonical

    async def _get_subscription_record(
        self,
        chat_id: int,
        channel_id: int,
        *,
        include_inactive: bool = True,
        request_id: str | None = None,
    ) -> Subscription | None:
        correlation_id = request_id or new_request_id()
        subscriptions = await self._fetch_subscription_rows(
            chat_id,
            channel_id,
            include_inactive=include_inactive,
            limit=2,
            request_id=correlation_id,
        )
        return await self._ensure_single_subscription(
            subscriptions,
            chat_id=chat_id,
            channel_id=channel_id,
            request_id=correlation_id,
        )

    async def create_subscription(
        self, chat_id: int, channel_id: int, *, request_id: str | None = None
    ) -> Subscription:
        """Create or reactivate a subscription."""
        correlation_id = request_id or new_request_id()
        subscription = await self._get_subscription_record(
            chat_id, channel_id, request_id=correlation_id
        )
        if subscription:
            subscription.is_active = True
            subscription.notification_enabled = True
            await self.session.commit()
            await self.session.refresh(subscription)
            _repo_log(
                logging.DEBUG,
                "Reactivated subscription",
                request_id=correlation_id,
                operation="repository.create_subscription",
                chat_id=chat_id,
                channel_id=channel_id,
                subscription_id=subscription.id,
                extra={"meta_reactivated": True},
            )
            return subscription

        subscription = Subscription(
            chat_id=chat_id,
            channel_id=channel_id,
        )
        self.session.add(subscription)
        await self.session.commit()
        await self.session.refresh(subscription)
        _repo_log(
            logging.DEBUG,
            "Created subscription",
            request_id=correlation_id,
            operation="repository.create_subscription",
            chat_id=chat_id,
            channel_id=channel_id,
            subscription_id=subscription.id,
            extra={"meta_reactivated": False},
        )
        return subscription

    async def get_chat_subscriptions(
        self, chat_id: int, *, request_id: str | None = None
    ) -> list[Subscription]:
        """Get all subscriptions for a chat."""
        correlation_id = request_id or new_request_id()
        operation = "repository.get_chat_subscriptions"
        result = await self.session.execute(
            select(Subscription)
                .where(Subscription.chat_id == chat_id)
                .where(Subscription.is_active)
                .options(selectinload(Subscription.channel))
        )
        subscriptions = list(result.scalars().all())
        _repo_log(
            logging.DEBUG,
            "Fetched chat subscriptions",
            request_id=correlation_id,
            operation=operation,
            chat_id=chat_id,
            extra={"meta_subscription_count": len(subscriptions)},
        )
        return subscriptions

    async def get_subscription(
        self, chat_id: int, channel_id: int, *, request_id: str | None = None
    ) -> Subscription | None:
        """Get a specific active subscription."""
        correlation_id = request_id or new_request_id()
        subscription = await self._get_subscription_record(
            chat_id,
            channel_id,
            include_inactive=False,
            request_id=correlation_id,
        )
        _repo_log(
            logging.DEBUG,
            "Fetched subscription record",
            request_id=correlation_id,
            operation="repository.get_subscription",
            chat_id=chat_id,
            channel_id=channel_id,
            subscription_id=getattr(subscription, "id", None),
            extra={"meta_found": bool(subscription)},
        )
        return subscription

    async def delete_subscription(
        self, chat_id: int, channel_id: int, *, request_id: str | None = None
    ) -> bool:
        """Soft delete a subscription."""
        correlation_id = request_id or new_request_id()
        subscriptions = await self._fetch_subscription_rows(
            chat_id,
            channel_id,
            include_inactive=True,
            request_id=correlation_id,
        )
        subscription = await self._ensure_single_subscription(
            subscriptions,
            chat_id=chat_id,
            channel_id=channel_id,
            request_id=correlation_id,
        )
        if subscription is None or not subscription.is_active:
            _repo_log(
                logging.DEBUG,
                "No active subscription to delete",
                request_id=correlation_id,
                operation="repository.delete_subscription",
                chat_id=chat_id,
                channel_id=channel_id,
            )
            return False

        subscription.is_active = False
        await self.session.commit()
        _repo_log(
            logging.DEBUG,
            "Subscription marked inactive",
            request_id=correlation_id,
            operation="repository.delete_subscription",
            chat_id=chat_id,
            channel_id=channel_id,
            subscription_id=subscription.id,
        )
        return True

    async def get_channel_subscribers(
        self, channel_id: int, *, request_id: str | None = None
    ) -> list[Subscription]:
        """Get all active subscribers for a channel."""
        correlation_id = request_id or new_request_id()
        operation = "repository.get_channel_subscribers"
        result = await self.session.execute(
            select(Subscription)
            .where(Subscription.channel_id == channel_id)
            .where(Subscription.is_active)
            .where(Subscription.notification_enabled)
            .options(selectinload(Subscription.chat))
        )
        subscribers = list(result.scalars().all())
        _repo_log(
            logging.DEBUG,
            "Fetched channel subscribers",
            request_id=correlation_id,
            operation=operation,
            channel_id=channel_id,
            extra={"meta_subscriber_count": len(subscribers)},
        )
        return subscribers


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
        thumbnail_url: str | None = None,
    ) -> Video:
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
        result = await self.session.execute(select(Video).where(Video.video_id == video_id))
        return result.scalar_one_or_none()

    async def get_channel_videos(self, channel_id: int, limit: int = 10) -> list[Video]:
        result = await self.session.execute(
            select(Video)
            .where(Video.channel_id == channel_id)
            .order_by(Video.published_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


class NotificationRepository:
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_notification(
        self,
        chat_id: int,
        video_id: int,
        message_id: str | None = None,
    ) -> Notification:
        notification = Notification(
            chat_id=chat_id,
            video_id=video_id,
            message_id=message_id,
        )
        self.session.add(notification)
        await self.session.commit()
        await self.session.refresh(notification)
        return notification

    async def get_chat_notifications(self, chat_id: int, limit: int = 10) -> list[Notification]:
        result = await self.session.execute(
            select(Notification)
            .where(Notification.chat_id == chat_id)
            .options(selectinload(Notification.video))
            .order_by(Notification.sent_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())
