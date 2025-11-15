from __future__ import annotations

import logging
from dataclasses import dataclass

import sqlalchemy as sa
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..database.models import Subscription, YouTubeChannel
from ..utils.config import settings
from .pubsub import PubSubManager


logger = logging.getLogger(__name__)


@dataclass(slots=True)
class ChannelSubscriptionState:
    """Lightweight snapshot of a channel's webhook subscription state."""

    pk: int
    channel_id: str
    subscription_webhook_url: str | None


class WebhookSubscriptionSynchronizer:
    """Refresh PubSub subscriptions when the webhook callback URL changes."""

    LEGACY_WEBHOOK_URL = "https://youtube-bot.nmro.cc/webhook/youtube/"

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self._session_factory = session_factory
        self._current_webhook = settings.webhook_callback_url

    async def run(self) -> None:
        """Synchronize PubSub subscriptions with the configured webhook URL."""
        async with self._session_factory() as session:
            channels = await self._load_active_channels(session)
            to_refresh = [
                channel
                for channel in channels
                if self._effective_webhook(channel) != self._current_webhook
            ]

            if not to_refresh:
                logger.info("Webhook synchronizer: all active subscriptions already use %s", self._current_webhook)
                return

            logger.info(
                "Webhook synchronizer: refreshing %d channel subscription(s) to %s",
                len(to_refresh),
                self._current_webhook,
            )

            new_manager = PubSubManager(self._current_webhook)
            legacy_managers: dict[str, PubSubManager] = {}

            try:
                for channel in to_refresh:
                    await self._refresh_channel(session, channel, legacy_managers, new_manager)
            finally:
                await new_manager.close()
                for manager in legacy_managers.values():
                    await manager.close()

    async def _load_active_channels(self, session: AsyncSession) -> list[ChannelSubscriptionState]:
        """Return channels that currently have at least one active subscriber."""
        stmt = (
            select(
                YouTubeChannel.id,
                YouTubeChannel.channel_id,
                sa.func.max(Subscription.webhook_url),
            )
            .join(Subscription, Subscription.channel_id == YouTubeChannel.id)
            .where(Subscription.is_active)
            .where(Subscription.notification_enabled)
            .group_by(YouTubeChannel.id, YouTubeChannel.channel_id)
        )
        result = await session.execute(stmt)
        return [
            ChannelSubscriptionState(
                pk=row[0],
                channel_id=row[1],
                subscription_webhook_url=row[2],
            )
            for row in result.all()
        ]

    def _effective_webhook(self, channel: ChannelSubscriptionState) -> str:
        """Return the webhook URL we believe PubSub is using for the channel."""
        return channel.subscription_webhook_url or self.LEGACY_WEBHOOK_URL

    async def _refresh_channel(
        self,
        session: AsyncSession,
        channel: ChannelSubscriptionState,
        legacy_managers: dict[str, PubSubManager],
        new_manager: PubSubManager,
    ) -> None:
        """Unsubscribe from the old callback and subscribe with the new callback."""
        previous_webhook = self._effective_webhook(channel)
        if previous_webhook == self._current_webhook:
            return

        logger.info(
            "Refreshing webhook for channel %s (previous=%s, new=%s)",
            channel.channel_id,
            previous_webhook,
            self._current_webhook,
        )

        legacy_manager = legacy_managers.get(previous_webhook)
        if legacy_manager is None:
            legacy_manager = PubSubManager(previous_webhook)
            legacy_managers[previous_webhook] = legacy_manager

        unsubscribe_ok = await legacy_manager.unsubscribe_from_channel(channel.channel_id)
        if not unsubscribe_ok:
            logger.warning(
                "Failed to unsubscribe channel %s from legacy webhook %s; continuing",
                channel.channel_id,
                previous_webhook,
            )

        subscribe_ok = await new_manager.subscribe_to_channel(channel.channel_id)
        if not subscribe_ok:
            logger.error(
                "Failed to subscribe channel %s to new webhook %s",
                channel.channel_id,
                self._current_webhook,
            )
            return

        await session.execute(
            sa.update(Subscription)
            .where(Subscription.channel_id == channel.pk)
            .where(Subscription.is_active)
            .where(Subscription.notification_enabled)
            .values(webhook_url=self._current_webhook)
        )
        await session.commit()
        logger.info("Channel %s now tracks webhook %s", channel.channel_id, self._current_webhook)
