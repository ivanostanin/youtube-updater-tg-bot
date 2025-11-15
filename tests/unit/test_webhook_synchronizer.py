from __future__ import annotations

from dataclasses import dataclass

import allure
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from src.database.models import Chat, Subscription, YouTubeChannel
from src.webhooks.synchronizer import WebhookSubscriptionSynchronizer


@dataclass
class _FakeManager:
    webhook_url: str
    subscribe_calls: list[str]
    unsubscribe_calls: list[str]
    closed: bool = False

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.subscribe_calls = []
        self.unsubscribe_calls = []
        self.closed = False

    async def subscribe_to_channel(self, channel_id: str) -> bool:
        self.subscribe_calls.append(channel_id)
        return True

    async def unsubscribe_from_channel(self, channel_id: str) -> bool:
        self.unsubscribe_calls.append(channel_id)
        return True

    async def close(self) -> None:
        self.closed = True


@allure.feature("Webhooks")
@allure.story("Webhook synchronizer")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_synchronizer_skips_channels_with_matching_webhook(
    async_db_engine,
    monkeypatch,
):
    """No PubSub calls should be made when stored URL already matches current settings."""
    session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        channel = YouTubeChannel(
            channel_id="UCnoop",
            channel_name="Noop Channel",
            channel_url="https://youtube.com/channel/UCnoop",
        )
        chat = Chat(chat_id="noop", chat_type="private", title="noop")
        session.add_all([channel, chat])
        await session.flush()

        session.add(
            Subscription(
                chat_id=chat.id,
                channel_id=channel.id,
                is_active=True,
                notification_enabled=True,
                webhook_url="https://current.example/webhook",
            )
        )
        await session.commit()

    created_managers: list[_FakeManager] = []

    def manager_factory(url: str) -> _FakeManager:
        manager = _FakeManager(url)
        created_managers.append(manager)
        return manager

    monkeypatch.setattr("src.webhooks.synchronizer.PubSubManager", manager_factory)
    from src.webhooks import synchronizer as synchronizer_module  # noqa: PLC0415

    monkeypatch.setattr(synchronizer_module.settings, "webhook_callback_url", "https://current.example/webhook")

    sync = WebhookSubscriptionSynchronizer(session_maker)
    await sync.run()

    assert created_managers == []


@allure.feature("Webhooks")
@allure.story("Webhook synchronizer")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_synchronizer_updates_channels_with_legacy_webhook(
    async_db_engine,
    monkeypatch,
):
    """Channels missing a webhook URL should be re-registered with the new callback."""
    session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    async with session_maker() as session:
        channel = YouTubeChannel(
            channel_id="UClegacy",
            channel_name="Legacy Channel",
            channel_url="https://youtube.com/channel/UClegacy",
        )
        chat = Chat(chat_id="legacy", chat_type="private", title="legacy")
        session.add_all([channel, chat])
        await session.flush()

        session.add(
            Subscription(
                chat_id=chat.id,
                channel_id=channel.id,
                is_active=True,
                notification_enabled=True,
                webhook_url=None,
            )
        )
        await session.commit()

    created_managers: list[_FakeManager] = []

    def manager_factory(url: str) -> _FakeManager:
        manager = _FakeManager(url)
        created_managers.append(manager)
        return manager

    monkeypatch.setattr("src.webhooks.synchronizer.PubSubManager", manager_factory)
    from src.webhooks import synchronizer as synchronizer_module  # noqa: PLC0415

    monkeypatch.setattr(synchronizer_module.settings, "webhook_callback_url", "https://new.example/webhook")

    sync = WebhookSubscriptionSynchronizer(session_maker)
    await sync.run()

    # First manager is for the new webhook URL (initialized eagerly)
    assert created_managers[0].webhook_url == "https://new.example/webhook"
    # Second manager handles the legacy callback inferred for the channel
    assert created_managers[1].webhook_url == sync.LEGACY_WEBHOOK_URL
    assert created_managers[0].subscribe_calls == ["UClegacy"]
    assert created_managers[1].unsubscribe_calls == ["UClegacy"]

    async with session_maker() as session:
        row = await session.execute(
            select(Subscription).where(Subscription.channel_id == channel.id)
        )
        subscription = row.scalar_one()
        assert subscription.webhook_url == "https://new.example/webhook"
