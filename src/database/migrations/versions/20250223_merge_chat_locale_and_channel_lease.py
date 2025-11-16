"""Merge heads: chat locale and channel lease metadata."""

from __future__ import annotations


revision = "20250223_merge_chat_locale_and_channel_lease"
down_revision = ("20250205_add_chat_locale", "20250221_channel_lease_metadata")
branch_labels = None
depends_on = None


def upgrade() -> None:
    """No-op merge migration."""


def downgrade() -> None:
    """Downgrade is a no-op; handled by individual branches."""
