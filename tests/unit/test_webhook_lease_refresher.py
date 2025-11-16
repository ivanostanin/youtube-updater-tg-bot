"""Unit tests for the webhook lease refresher worker."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import allure
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.repository import ChannelRepository, ChatRepository, SubscriptionRepository
from src.utils import metrics
from src.webhooks.lease_refresher import WebhookLeaseRefresher


pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("reset_pubsub_metrics")]


class _FakeManager:
    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.subscribe_calls: list[str] = []
        self.closed = False

    async def subscribe_to_channel(self, channel_id: str) -> bool:
        self.subscribe_calls.append(channel_id)
        return True

    async def close(self) -> None:
        self.closed = True


def _metric_value(counter, labels: dict[str, str]) -> float:
    """Return the sample value for the given labels."""
    for metric in counter.collect():
        for sample in metric.samples:
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return sample.value
    return 0.0


@allure.feature("Webhooks")
@allure.story("Lease refresher")
@allure.severity(allure.severity_level.CRITICAL)
async def test_lease_refresher_renews_candidates(async_db_engine, monkeypatch):
    """Channels nearing expiry should be renewed and metadata updated."""
    session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        chat_repo = ChatRepository(session)
        channel_repo = ChannelRepository(session)
        sub_repo = SubscriptionRepository(session)

        chat = await chat_repo.get_or_create_chat(
            chat_id="lease-refresh",
            chat_type="private",
            title="Lease Refresh",
        )
        channel = await channel_repo.get_or_create_channel(
            channel_id="UCrenew",
            channel_name="Renew Me",
            channel_url="https://youtube.com/channel/UCrenew",
        )
        await sub_repo.create_subscription(chat.id, channel.id)
        channel.webhook_callback_url = "https://old.example/webhook"
        channel.webhook_lease_seconds = 3600
        channel.webhook_lease_expires_at = datetime.now(UTC) + timedelta(minutes=5)
        await session.commit()

    fake_manager = _FakeManager("https://new.example/webhook")
    monkeypatch.setattr("src.webhooks.lease_refresher.PubSubManager", lambda url: fake_manager)

    refresher = WebhookLeaseRefresher(
        session_maker,
        webhook_callback_url="https://new.example/webhook",
        renewal_threshold_seconds=600,
        batch_limit=10,
    )

    await refresher.run()

    assert fake_manager.subscribe_calls == ["UCrenew"]

    async with session_maker() as session:
        channel = await ChannelRepository(session).get_channel_by_id("UCrenew")
        assert channel is not None
        assert channel.webhook_callback_url == "https://new.example/webhook"
        assert channel.webhook_lease_seconds == 3600
        assert channel.webhook_lease_expires_at is not None
        expires_at = channel.webhook_lease_expires_at
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        assert expires_at > datetime.now(UTC)

    assert (
        _metric_value(
            metrics.WEBHOOK_LEASE_REFRESH_TOTAL,
            {"result": "attempt"},
        )
        == 1.0
    )
    assert (
        _metric_value(
            metrics.WEBHOOK_LEASE_REFRESH_TOTAL,
            {"result": "success"},
        )
        == 1.0
    )


@allure.feature("Webhooks")
@allure.story("Lease refresher")
@allure.severity(allure.severity_level.NORMAL)
async def test_lease_refresher_skips_when_no_candidates(async_db_engine, monkeypatch):
    """Worker should no-op when no channels need refreshing."""
    session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        chat_repo = ChatRepository(session)
        channel_repo = ChannelRepository(session)
        sub_repo = SubscriptionRepository(session)

        chat = await chat_repo.get_or_create_chat(
            chat_id="lease-skip",
            chat_type="private",
            title="Lease Skip",
        )
        channel = await channel_repo.get_or_create_channel(
            channel_id="UCskip",
            channel_name="Skip Me",
            channel_url="https://youtube.com/channel/UCskip",
        )
        await sub_repo.create_subscription(chat.id, channel.id)
        channel.webhook_callback_url = "https://bot.example/webhook"
        channel.webhook_lease_seconds = 3600
        channel.webhook_lease_expires_at = datetime.now(UTC) + timedelta(hours=5)
        await session.commit()

    fake_manager = _FakeManager("https://bot.example/webhook")
    monkeypatch.setattr("src.webhooks.lease_refresher.PubSubManager", lambda url: fake_manager)

    refresher = WebhookLeaseRefresher(
        session_maker,
        webhook_callback_url="https://bot.example/webhook",
        renewal_threshold_seconds=600,
        batch_limit=10,
    )

    await refresher.run()
    assert fake_manager.subscribe_calls == []

    assert (
        _metric_value(
            metrics.WEBHOOK_LEASE_REFRESH_TOTAL,
            {"result": "skipped"},
        )
        == 1.0
    )
