from datetime import UTC, datetime

import pytest

from src.database.models import ChannelAdminLink, Chat, User
from src.database.repository import ChannelAdminLinkRepository


@pytest.mark.unit
async def test_channel_admin_link_upsert_and_revoke(async_db_session):
    repo = ChannelAdminLinkRepository(async_db_session)
    user = User(telegram_id="555", username="repo_user")
    channel = Chat(chat_id="-100123", chat_type="channel", title="Repo Channel")
    async_db_session.add_all([user, channel])
    await async_db_session.flush()

    link = await repo.upsert_link(
        channel_chat_id=channel.id,
        admin_user_id=user.id,
        role="administrator",
        last_verified_at=datetime.now(UTC),
    )
    assert link.revoked_at is None

    listed = await repo.list_active_links_for_user(user.id)
    assert len(listed) == 1

    await repo.mark_revoked(channel_chat_id=channel.id, admin_user_id=user.id)
    refreshed = await repo.get_active_link(
        channel_chat_id=channel.id,
        admin_user_id=user.id,
    )
    assert refreshed is None


@pytest.mark.unit
async def test_channel_admin_link_upsert_reactivates(async_db_session):
    repo = ChannelAdminLinkRepository(async_db_session)
    user = User(telegram_id="556", username="reactivate")
    channel = Chat(chat_id="-100124", chat_type="channel", title="Reactivate Channel")
    async_db_session.add_all([user, channel])
    await async_db_session.flush()

    first = ChannelAdminLink(
        channel_chat_id=channel.id,
        admin_user_id=user.id,
        role="administrator",
        revoked_at=datetime.now(UTC),
    )
    async_db_session.add(first)
    await async_db_session.commit()

    link = await repo.upsert_link(
        channel_chat_id=channel.id,
        admin_user_id=user.id,
        role="administrator",
    )
    assert link.revoked_at is None
