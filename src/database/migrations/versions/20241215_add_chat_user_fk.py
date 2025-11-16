"""Add optional user relationship to chats."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import MetaData, select
from sqlalchemy.engine import Connection


revision = "20241215_chat_user_fk"
down_revision = "20241202_chat_support"
branch_labels = None
depends_on = None


def _backfill_chat_users(connection: Connection) -> None:
    metadata = MetaData()
    metadata.reflect(bind=connection, only=("chats", "users"))

    chats = metadata.tables["chats"]
    users = metadata.tables["users"]

    join_stmt = (
        select(
            chats.c.id,
            chats.c.chat_type,
            users.c.id.label("user_pk"),
        )
        .select_from(
            chats.outerjoin(users, users.c.telegram_id == chats.c.chat_id),
        )
        .where(chats.c.chat_type == "private")
    )

    rows = connection.execute(join_stmt).all()
    for row in rows:
        if row.user_pk is None:
            continue
        connection.execute(sa.update(chats).where(chats.c.id == row.id).values(user_id=row.user_pk))


def upgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_chats_user_id_users",
            "users",
            ["user_id"],
            ["id"],
            ondelete="SET NULL",
        )

    connection = op.get_bind()
    _backfill_chat_users(connection)


def downgrade() -> None:
    with op.batch_alter_table("chats") as batch_op:
        batch_op.drop_constraint("fk_chats_user_id_users", type_="foreignkey")
        batch_op.drop_column("user_id")
