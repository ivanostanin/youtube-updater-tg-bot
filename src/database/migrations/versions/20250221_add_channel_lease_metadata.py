"""Add lease metadata fields to YouTube channels."""

from __future__ import annotations

import os

import sqlalchemy as sa
from alembic import op
from sqlalchemy import select
from sqlalchemy.engine import Connection


revision = "20250221_channel_lease_metadata"
down_revision = "20250119_subscription_webhook_url"
branch_labels = None
depends_on = None


def _fallback_callback_url() -> str:
    """Return the best-effort callback URL for backfills."""
    return os.environ.get("WEBHOOK_CALLBACK_URL") or "http://localhost:8000/webhook/youtube"


def _backfill_callback_urls(connection: Connection) -> None:
    metadata = sa.MetaData()
    metadata.reflect(bind=connection, only=("youtube_channels", "subscriptions"))

    channels = metadata.tables["youtube_channels"]
    subscriptions = metadata.tables["subscriptions"]

    # Build lookup of latest known webhook callback per channel.
    callback_rows = connection.execute(
        select(
            subscriptions.c.channel_id,
            subscriptions.c.webhook_url,
            subscriptions.c.created_at,
            subscriptions.c.id,
        )
        .where(subscriptions.c.webhook_url.is_not(None))
        .order_by(
            subscriptions.c.channel_id,
            subscriptions.c.created_at.desc(),
            subscriptions.c.id.desc(),
        )
    ).all()

    callback_lookup: dict[int, str | None] = {}
    for channel_id, webhook_url, *_ in callback_rows:
        if channel_id not in callback_lookup and webhook_url:
            callback_lookup[channel_id] = webhook_url

    fallback = _fallback_callback_url()

    for (channel_id,) in connection.execute(select(channels.c.id)).all():
        callback = callback_lookup.get(channel_id) or fallback
        connection.execute(
            sa.update(channels)
            .where(channels.c.id == channel_id)
            .values(webhook_callback_url=callback)
        )


def upgrade() -> None:
    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.add_column(sa.Column("webhook_callback_url", sa.String(length=512), nullable=True))
        batch_op.add_column(sa.Column("webhook_lease_seconds", sa.Integer(), nullable=True))
        batch_op.add_column(
            sa.Column("webhook_lease_expires_at", sa.DateTime(timezone=True), nullable=True)
        )
        batch_op.add_column(
            sa.Column("webhook_last_verified_at", sa.DateTime(timezone=True), nullable=True)
        )

    connection = op.get_bind()
    _backfill_callback_urls(connection)


def downgrade() -> None:
    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.drop_column("webhook_last_verified_at")
        batch_op.drop_column("webhook_lease_expires_at")
        batch_op.drop_column("webhook_lease_seconds")
        batch_op.drop_column("webhook_callback_url")
