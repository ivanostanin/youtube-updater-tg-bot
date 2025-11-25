"""Unit tests for webhook handler lease capture."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from unittest.mock import MagicMock

import allure
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from starlette.requests import Request

from src.database.models import YouTubeChannel
from src.utils import metrics
from src.webhooks.constants import DEFAULT_PUBSUB_LEASE_SECONDS
from src.webhooks.handlers import WebhookHandlers


pytestmark = [pytest.mark.unit, pytest.mark.usefixtures("reset_pubsub_metrics")]


def _build_request(query: str, *, scheme: str = "https", host: str = "testserver") -> Request:
    """Create a Starlette request object for testing."""

    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": scheme,
        "path": "/webhook/youtube",
        "raw_path": b"/webhook/youtube",
        "query_string": query.encode(),
        "headers": [(b"host", host.encode())],
        "client": ("127.0.0.1", 1234),
        "server": (host, 443),
    }

    async def _receive() -> dict[str, object]:
        return {"type": "http.request", "body": b"", "more_body": False}

    return Request(scope, _receive)


def _metric_value(counter, labels: dict[str, str]) -> float:
    """Return the sample value for the given labels."""
    for metric in counter.collect():
        for sample in metric.samples:
            if all(sample.labels.get(key) == value for key, value in labels.items()):
                return cast(float, sample.value)
    return 0.0


@allure.feature("Webhooks")
@allure.story("Lease metadata")
@allure.severity(allure.severity_level.CRITICAL)
async def test_webhook_handler_stores_lease_metadata(async_db_engine, monkeypatch):
    """Verification requests should persist lease metadata even without lease_seconds."""
    session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr("src.webhooks.handlers.AsyncSessionLocal", session_maker)

    channel: YouTubeChannel | None

    async with session_maker() as session:
        channel = YouTubeChannel(
            channel_id="UClease",
            channel_name="Lease Channel",
            channel_url="https://youtube.com/channel/UClease",
        )
        session.add(channel)
        await session.commit()

    handlers = WebhookHandlers(notification_service=MagicMock())
    request = _build_request(
        "hub.mode=subscribe&hub.topic=https%3A%2F%2Fwww.youtube.com%2Fxml%2Ffeeds%2Fvideos.xml%3Fchannel_id%3DUClease&hub.challenge=test-challenge"
    )

    response = await handlers._handle_verification_challenge(
        request,
        "test-challenge",
        request_id="unit-test",
    )
    assert response.status_code == 200
    assert response.body == b"test-challenge"

    async with session_maker() as session:
        channel = await session.get(YouTubeChannel, 1)
        assert channel is not None
        assert channel.webhook_callback_url == "https://testserver/webhook/youtube"
        assert channel.webhook_lease_seconds == DEFAULT_PUBSUB_LEASE_SECONDS
        assert channel.webhook_last_verified_at is not None
        expires_at = channel.webhook_lease_expires_at
        assert expires_at is not None
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=UTC)
        assert expires_at > datetime.now(UTC)

    assert (
        _metric_value(
            metrics.WEBHOOK_VERIFICATION_CHALLENGES,
            {"mode": "subscribe", "result": "stored"},
        )
        == 1.0
    )


@allure.feature("Webhooks")
@allure.story("Lease metadata")
@allure.severity(allure.severity_level.NORMAL)
async def test_webhook_handler_clears_metadata_on_unsubscribe(async_db_engine, monkeypatch):
    """unsubscribe challenges should clear lease state."""
    session_maker = async_sessionmaker(
        async_db_engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    monkeypatch.setattr("src.webhooks.handlers.AsyncSessionLocal", session_maker)

    async with session_maker() as session:
        channel = YouTubeChannel(
            channel_id="UCclear",
            channel_name="Clear Channel",
            channel_url="https://youtube.com/channel/UCclear",
            webhook_callback_url="https://bot.example/webhook",
            webhook_lease_seconds=1000,
            webhook_lease_expires_at=datetime.now(UTC),
            webhook_last_verified_at=datetime.now(UTC),
        )
        session.add(channel)
        await session.commit()

    handlers = WebhookHandlers(notification_service=MagicMock())
    request = _build_request(
        "hub.mode=unsubscribe&hub.topic=https%3A%2F%2Fwww.youtube.com%2Fxml%2Ffeeds%2Fvideos.xml%3Fchannel_id%3DUCclear&hub.challenge=bye"
    )

    response = await handlers._handle_verification_challenge(
        request,
        "bye",
        request_id="unit-test",
    )
    assert response.status_code == 200
    assert response.body == b"bye"

    async with session_maker() as session:
        channel_from_db_obj = await session.get(YouTubeChannel, 1)
        assert channel_from_db_obj is not None
        assert channel_from_db_obj.webhook_callback_url is None
        assert channel_from_db_obj.webhook_lease_seconds is None
        assert channel_from_db_obj.webhook_lease_expires_at is None
        assert channel_from_db_obj.webhook_last_verified_at is None

    assert (
        _metric_value(
            metrics.WEBHOOK_VERIFICATION_CHALLENGES,
            {"mode": "unsubscribe", "result": "cleared"},
        )
        == 1.0
    )
