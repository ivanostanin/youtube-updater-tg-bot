"""Add webhook_url column to YouTube channels."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20250118_channel_webhook_url"
down_revision = "20241215_chat_user_fk"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.add_column(sa.Column("webhook_url", sa.String(length=512), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("youtube_channels") as batch_op:
        batch_op.drop_column("webhook_url")
