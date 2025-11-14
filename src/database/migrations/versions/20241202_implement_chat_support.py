"""Introduce chat model and migrate subscriptions/notifications to chat context."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from alembic import op
from sqlalchemy import select
from sqlalchemy.engine import Connection
from sqlalchemy.sql.schema import Table


revision = "20241202_chat_support"
down_revision = None
branch_labels = None
depends_on = None


def _insert_chat(
    connection: Connection,
    chats_table: Table,
    *,
    chat_id: str,
    chat_type: str,
    title: str | None,
    created_at: datetime | None,
) -> int:
    insert_stmt = sa.insert(chats_table).values(
        chat_id=chat_id,
        chat_type=chat_type,
        title=title,
        created_at=created_at or datetime.utcnow(),
        is_active=True,
    )
    result = connection.execute(insert_stmt)
    pk = result.inserted_primary_key
    if pk:
        return int(pk[0])

    select_stmt = select(chats_table.c.id).where(chats_table.c.chat_id == chat_id)
    return int(connection.execute(select_stmt).scalar_one())


def _get_or_create_user(
    connection: Connection,
    users_table: Table,
    *,
    telegram_id: str,
    title: str | None,
) -> int:
    existing = connection.execute(
        select(users_table.c.id).where(users_table.c.telegram_id == telegram_id)
    ).scalar_one_or_none()
    if existing is not None:
        return int(existing)

    insert_stmt = sa.insert(users_table).values(
        telegram_id=telegram_id,
        username=title,
        first_name=title,
        last_name=None,
        created_at=datetime.utcnow(),
        is_active=True,
    )
    result = connection.execute(insert_stmt)
    pk = result.inserted_primary_key
    if pk:
        return int(pk[0])

    return int(
        connection.execute(
            select(users_table.c.id).where(users_table.c.telegram_id == telegram_id)
        ).scalar_one()
    )


def upgrade() -> None:
    op.create_table(
        "chats",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.String(length=128), nullable=False),
        sa.Column("chat_type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
    )
    op.create_index("ix_chats_chat_id", "chats", ["chat_id"], unique=True)

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.add_column(sa.Column("chat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_subscriptions_chat_id_chats",
            "chats",
            ["chat_id"],
            ["id"],
            ondelete="CASCADE",
        )

    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("chat_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notifications_chat_id_chats",
            "chats",
            ["chat_id"],
            ["id"],
            ondelete="CASCADE",
        )

    connection = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection, only=("users", "subscriptions", "notifications", "chats")
    )

    users_table = metadata.tables["users"]
    subscriptions_table = metadata.tables["subscriptions"]
    notifications_table = metadata.tables["notifications"]
    chats_table = metadata.tables["chats"]

    user_rows = connection.execute(
        select(
            users_table.c.id,
            users_table.c.telegram_id,
            users_table.c.username,
            users_table.c.first_name,
            users_table.c.last_name,
            users_table.c.created_at,
        )
    ).all()

    user_to_chat: dict[int, int] = {}

    for user in user_rows:
        title_candidates = [
            user.username,
            user.first_name,
            user.last_name,
        ]
        title = next((value for value in title_candidates if value), None)
        chat_identifier = str(user.telegram_id)

        chat_pk = _insert_chat(
            connection,
            chats_table,
            chat_id=chat_identifier,
            chat_type="private",
            title=title,
            created_at=user.created_at or datetime.utcnow(),
        )

        user_to_chat[user.id] = chat_pk

    subscription_rows = connection.execute(
        select(subscriptions_table.c.id, subscriptions_table.c.user_id)
    ).all()

    for subscription in subscription_rows:
        chat_fk = user_to_chat.get(subscription.user_id)
        if chat_fk is None:
            continue

        connection.execute(
            sa.update(subscriptions_table)
            .where(subscriptions_table.c.id == subscription.id)
            .values(chat_id=chat_fk)
        )

    notification_rows = connection.execute(
        select(notifications_table.c.id, notifications_table.c.user_id)
    ).all()

    for notification in notification_rows:
        chat_fk = user_to_chat.get(notification.user_id)
        if chat_fk is None:
            continue

        connection.execute(
            sa.update(notifications_table)
            .where(notifications_table.c.id == notification.id)
            .values(chat_id=chat_fk)
        )

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.alter_column("chat_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("user_id")
        batch_op.create_unique_constraint(
            "uq_subscriptions_chat_channel_active", ["chat_id", "channel_id", "is_active"]
        )

    op.create_index("ix_subscriptions_chat_id", "subscriptions", ["chat_id"])

    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.alter_column("chat_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_column("user_id")

    op.create_index("ix_notifications_chat_id", "notifications", ["chat_id"])


def downgrade() -> None:
    op.drop_index("ix_notifications_chat_id", table_name="notifications")
    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_notifications_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    op.drop_index("ix_subscriptions_chat_id", table_name="subscriptions")
    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.drop_constraint("uq_subscriptions_chat_channel_active", type_="unique")
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_subscriptions_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="CASCADE",
        )

    connection = op.get_bind()
    metadata = sa.MetaData()
    metadata.reflect(
        bind=connection, only=("users", "subscriptions", "notifications", "chats")
    )

    users_table = metadata.tables["users"]
    subscriptions_table = metadata.tables["subscriptions"]
    notifications_table = metadata.tables["notifications"]
    chats_table = metadata.tables["chats"]

    chat_rows = connection.execute(
        select(
            chats_table.c.id,
            chats_table.c.chat_id,
            chats_table.c.chat_type,
            chats_table.c.title,
        )
    ).all()

    chat_to_user: dict[int, int] = {}

    for chat in chat_rows:
        user_pk = _get_or_create_user(
            connection,
            users_table,
            telegram_id=str(chat.chat_id),
            title=chat.title,
        )
        chat_to_user[chat.id] = user_pk

    subscription_rows = connection.execute(
        select(subscriptions_table.c.id, subscriptions_table.c.chat_id)
    ).all()

    for subscription in subscription_rows:
        user_fk = chat_to_user.get(subscription.chat_id)
        if user_fk is None:
            continue

        connection.execute(
            sa.update(subscriptions_table)
            .where(subscriptions_table.c.id == subscription.id)
            .values(user_id=user_fk)
        )

    notification_rows = connection.execute(
        select(notifications_table.c.id, notifications_table.c.chat_id)
    ).all()

    for notification in notification_rows:
        user_fk = chat_to_user.get(notification.chat_id)
        if user_fk is None:
            continue

        connection.execute(
            sa.update(notifications_table)
            .where(notifications_table.c.id == notification.id)
            .values(user_id=user_fk)
        )

    with op.batch_alter_table("notifications", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("fk_notifications_chat_id_chats", type_="foreignkey")
        batch_op.drop_column("chat_id")

    with op.batch_alter_table("subscriptions", schema=None) as batch_op:
        batch_op.alter_column("user_id", existing_type=sa.Integer(), nullable=False)
        batch_op.drop_constraint("fk_subscriptions_chat_id_chats", type_="foreignkey")
        batch_op.drop_column("chat_id")

    op.drop_index("ix_chats_chat_id", table_name="chats")
    op.drop_table("chats")
