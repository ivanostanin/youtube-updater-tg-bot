"""Move webhook tracking from channels to subscriptions."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import select
from sqlalchemy.engine import Connection


revision = "20250119_subscription_webhook_url"
down_revision = "20250118_channel_webhook_url"
branch_labels = None
depends_on = None


def _copy_channel_webhooks_to_subscriptions(connection: Connection) -> None:
    metadata = sa.MetaData()
    metadata.reflect(bind=connection, only=("subscriptions", "youtube_channels"))

    subscriptions = metadata.tables["subscriptions"]
    channels = metadata.tables["youtube_channels"]

    join_stmt = (
        select(subscriptions.c.id, channels.c.webhook_url)
        .select_from(subscriptions.join(channels, subscriptions.c.channel_id == channels.c.id))
        .where(channels.c.webhook_url.is_not(None))
    )

    rows = connection.execute(join_stmt).all()
    for subscription_id, webhook_url in rows:
        connection.execute(
            sa.update(subscriptions)
            .where(subscriptions.c.id == subscription_id)
            .values(webhook_url=webhook_url)
        )


def _copy_subscription_webhooks_to_channels(connection: Connection) -> None:
    metadata = sa.MetaData()
    metadata.reflect(bind=connection, only=("subscriptions", "youtube_channels"))

    subscriptions = metadata.tables["subscriptions"]
    channels = metadata.tables["youtube_channels"]

    join_stmt = (
        select(
            channels.c.id,
            sa.func.max(subscriptions.c.webhook_url),
        )
        .select_from(
            channels.outerjoin(subscriptions, subscriptions.c.channel_id == channels.c.id),
        )
        .group_by(channels.c.id)
    )

    rows = connection.execute(join_stmt).all()
    for channel_id, webhook_url in rows:
        if webhook_url is None:
            continue
        connection.execute(
            sa.update(channels).where(channels.c.id == channel_id).values(webhook_url=webhook_url)
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("subscriptions")]

    if "webhook_url" not in columns:
        with op.batch_alter_table("subscriptions") as batch_op:
            batch_op.add_column(sa.Column("webhook_url", sa.String(length=512), nullable=True))

    connection = op.get_bind()
    _copy_channel_webhooks_to_subscriptions(connection)

    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.drop_column("webhook_url")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    yt_columns = [c["name"] for c in inspector.get_columns("youtube_channels")]
    sub_columns = [c["name"] for c in inspector.get_columns("subscriptions")]

    if "webhook_url" not in yt_columns:
        with op.batch_alter_table("youtube_channels") as batch_op:
            batch_op.add_column(sa.Column("webhook_url", sa.String(length=512), nullable=True))

    connection = op.get_bind()
    _copy_subscription_webhooks_to_channels(connection)

    if "webhook_url" in sub_columns:
        with op.batch_alter_table("subscriptions") as batch_op:
            batch_op.drop_column("webhook_url")
