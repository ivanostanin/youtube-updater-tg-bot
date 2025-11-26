"""Add preferred_locale column to chats."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision = "20250205_add_chat_locale"
down_revision = "20250119_subscription_webhook_url"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("chats")]

    if "preferred_locale" not in columns:
        with op.batch_alter_table("chats") as batch_op:
            batch_op.add_column(sa.Column("preferred_locale", sa.String(length=5), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("chats")]

    if "preferred_locale" in columns:
        with op.batch_alter_table("chats") as batch_op:
            batch_op.drop_column("preferred_locale")
