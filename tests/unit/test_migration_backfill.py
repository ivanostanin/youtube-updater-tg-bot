"""Regression tests for the lease metadata migration backfill."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from importlib import import_module

import pytest
import sqlalchemy as sa
from sqlalchemy.orm import Session

from src.database.models import Base, Chat, Subscription, YouTubeChannel


pytestmark = [pytest.mark.unit]

migration = import_module("src.database.migrations.versions.20250221_add_channel_lease_metadata")


def test_backfill_uses_most_recent_subscription_webhook() -> None:
    """The migration should copy the latest webhook_url per channel."""
    engine = sa.create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)

    with Session(engine) as session:
        channel = YouTubeChannel(
            channel_id="UCbackfill",
            channel_name="Backfill Target",
            channel_url="https://youtube.com/channel/UCbackfill",
        )
        chat = Chat(
            chat_id="chat-backfill",
            chat_type="private",
            title="Backfill Chat",
        )
        session.add_all([channel, chat])
        session.commit()

        older = Subscription(
            chat_id=chat.id,
            channel_id=channel.id,
            webhook_url="https://old.example/webhook",
            created_at=datetime.now(UTC) - timedelta(days=2),
        )
        newer = Subscription(
            chat_id=chat.id,
            channel_id=channel.id,
            webhook_url="https://new.example/webhook",
            created_at=datetime.now(UTC) - timedelta(days=1),
        )
        session.add_all([older, newer])
        session.commit()

        # Sanity check baseline.
        channel_row = session.get(YouTubeChannel, channel.id)
        assert channel_row is not None
        assert channel_row.webhook_callback_url is None

    with engine.begin() as connection:
        migration._backfill_callback_urls(connection)

    with Session(engine) as session:
        channel_row = session.get(YouTubeChannel, channel.id)
        assert channel_row is not None
        assert channel_row.webhook_callback_url == "https://new.example/webhook"
