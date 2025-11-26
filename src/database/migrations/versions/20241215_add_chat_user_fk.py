"""Add optional user relationship to chats."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy import MetaData, select
from sqlalchemy.engine import Connection


revision = "20241215_chat_user_fk"
down_revision = None
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
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("chats")]
    foreign_keys = [fk["name"] for fk in inspector.get_foreign_keys("chats")]

    if "user_id" not in columns:
        with op.batch_alter_table("chats") as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))

    connection = op.get_bind()
    _backfill_chat_users(connection)

    if "fk_chats_user_id_users" not in foreign_keys:
        with op.batch_alter_table("chats") as batch_op:
            batch_op.create_foreign_key(
                "fk_chats_user_id_users",
                "users",
                ["user_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = [c["name"] for c in inspector.get_columns("chats")]
    foreign_keys = [fk["name"] for fk in inspector.get_foreign_keys("chats")]

    with op.batch_alter_table("chats") as batch_op:
        if "fk_chats_user_id_users" in foreign_keys:
            batch_op.drop_constraint("fk_chats_user_id_users", type_="foreignkey")
        if "user_id" in columns:
            batch_op.drop_column("user_id")
