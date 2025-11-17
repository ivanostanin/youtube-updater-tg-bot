"""Add channel admin links and DM context fields."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op


revision = "20250305_channel_admin_dm_context"
down_revision = "20250223_merge_chat_locale_and_channel_lease"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    existing_tables = set(inspector.get_table_names())
    if "channel_admin_links" not in existing_tables:
        op.create_table(
            "channel_admin_links",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("channel_chat_id", sa.Integer(), sa.ForeignKey("chats.id"), nullable=False),
            sa.Column("admin_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("role", sa.String(length=32), nullable=False),
            sa.Column("linked_at", sa.DateTime(), server_default=sa.func.now(), nullable=False),
            sa.Column("last_verified_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("channel_chat_id", "admin_user_id", name="uq_channel_admin_link"),
        )

    chat_columns = {col["name"] for col in inspector.get_columns("chats")}
    chat_fk_names = {fk["name"] for fk in inspector.get_foreign_keys("chats") if fk.get("name")}

    needs_column = any(
        name not in chat_columns
        for name in (
            "active_channel_chat_id",
            "active_channel_selected_at",
            "active_channel_expires_at",
        )
    )
    needs_fk = "fk_chats_active_channel_chat_id" not in chat_fk_names

    if needs_column or needs_fk:
        with op.batch_alter_table("chats", recreate="always") as batch_op:
            if "active_channel_chat_id" not in chat_columns:
                batch_op.add_column(
                    sa.Column("active_channel_chat_id", sa.Integer(), nullable=True)
                )
            if "active_channel_selected_at" not in chat_columns:
                batch_op.add_column(
                    sa.Column("active_channel_selected_at", sa.DateTime(), nullable=True)
                )
            if "active_channel_expires_at" not in chat_columns:
                batch_op.add_column(
                    sa.Column("active_channel_expires_at", sa.DateTime(), nullable=True)
                )
            if needs_fk:
                batch_op.create_foreign_key(
                    "fk_chats_active_channel_chat_id",
                    "chats",
                    ["active_channel_chat_id"],
                    ["id"],
                )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    chat_columns = {col["name"] for col in inspector.get_columns("chats")}
    chat_fk_names = {fk["name"] for fk in inspector.get_foreign_keys("chats") if fk.get("name")}

    needs_column_drop = any(
        name in chat_columns
        for name in (
            "active_channel_chat_id",
            "active_channel_selected_at",
            "active_channel_expires_at",
        )
    )
    needs_fk_drop = "fk_chats_active_channel_chat_id" in chat_fk_names

    if needs_column_drop or needs_fk_drop:
        with op.batch_alter_table("chats", recreate="always") as batch_op:
            if needs_fk_drop:
                batch_op.drop_constraint("fk_chats_active_channel_chat_id", type_="foreignkey")
            if "active_channel_expires_at" in chat_columns:
                batch_op.drop_column("active_channel_expires_at")
            if "active_channel_selected_at" in chat_columns:
                batch_op.drop_column("active_channel_selected_at")
            if "active_channel_chat_id" in chat_columns:
                batch_op.drop_column("active_channel_chat_id")

    existing_tables = set(inspector.get_table_names())
    if "channel_admin_links" in existing_tables:
        op.drop_table("channel_admin_links")
