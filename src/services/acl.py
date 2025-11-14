from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable

from telegram import Bot
from telegram.error import TelegramError


class ACLService:
    """Service responsible for chat-level access control validation."""

    _GROUP_CHAT_TYPES = {"group", "supergroup", "channel"}

    def __init__(self, bot: Bot):
        self._bot = bot
        self._logger = logging.getLogger(__name__)

    def _normalize_numeric_id(self, value: int | str | None) -> int | None:
        """Normalize Telegram identifiers into integers for API calls."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except ValueError:
            self._logger.warning("Expected numeric identifier but received %s", value)
            return None

    @staticmethod
    def is_group_context(chat_type: str) -> bool:
        """Return True if the chat type represents a shared context."""
        return chat_type in ACLService._GROUP_CHAT_TYPES

    async def verify_admin(
        self, chat_id: int | str, user_id: int | str | None, chat_type: str
    ) -> bool:
        """Verify if the user is an administrator of the chat."""
        if not self.is_group_context(chat_type):
            return True

        if user_id is None:
            self._logger.warning("Unable to verify admin status: user_id is missing.")
            return False

        normalized_chat_id = self._normalize_numeric_id(chat_id)
        normalized_user_id = self._normalize_numeric_id(user_id)

        if normalized_chat_id is None or normalized_user_id is None:
            return False

        try:
            member = await self._bot.get_chat_member(
                chat_id=normalized_chat_id,
                user_id=normalized_user_id,
            )
        except TelegramError as error:
            self._logger.warning(
                f"Failed to verify admin status for chat {chat_id} and user {user_id}: {error}"
            )
            return False

        return member.status in {"administrator", "creator", "owner"}

    async def require_admin(
        self,
        *,
        chat_id: int | str,
        chat_type: str,
        user_id: int | str | None,
        on_denied: Callable[[str], Awaitable[None]],
    ) -> bool:
        """Ensure the acting user has admin rights; send feedback if not."""
        if not self.is_group_context(chat_type):
            return True

        if user_id is None:
            await on_denied(
                "I couldn't identify the user running this command. "
                "Please issue the command from your personal account while a member of this chat."
            )
            return False

        if await self.verify_admin(chat_id, user_id, chat_type):
            return True

        await on_denied("Only chat administrators can manage subscriptions here.")
        return False
