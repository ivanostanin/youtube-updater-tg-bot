from __future__ import annotations

from collections.abc import Awaitable, Callable

from telegram import Bot
from telegram.error import TelegramError

from ..utils.i18n import translate
from ..utils.logging import get_logger, log_context, new_request_id, sanitize_label


class ACLService:
    """Service responsible for chat-level access control validation."""

    _GROUP_CHAT_TYPES = {"group", "supergroup", "channel"}

    def __init__(self, bot: Bot):
        self._bot = bot
        self._logger = get_logger(__name__)

    def _normalize_numeric_id(
        self,
        value: int | str | None,
        *,
        request_id: str,
        operation: str,
        field: str,
    ) -> int | None:
        """Normalize Telegram identifiers into integers for API calls."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(value)
        except ValueError:
            self._logger.warning(
                "Expected numeric identifier but received incompatible value",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    meta_invalid_field=field,
                    meta_invalid_value=sanitize_label(str(value)),
                    chat_id=str(value) if field == "chat_id" else None,
                    user_id=str(value) if field == "user_id" else None,
                ),
            )
            return None

    @staticmethod
    def is_group_context(chat_type: str) -> bool:
        """Return True if the chat type represents a shared context."""
        return chat_type in ACLService._GROUP_CHAT_TYPES

    async def verify_admin(
        self,
        chat_id: int | str,
        user_id: int | str | None,
        chat_type: str,
        *,
        request_id: str | None = None,
    ) -> bool:
        """Verify if the user is an administrator of the chat."""
        correlation_id = request_id or new_request_id()
        operation = "acl.verify_admin"
        if not self.is_group_context(chat_type):
            self._logger.debug(
                "ACL verification skipped for private chat",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    chat_type=chat_type,
                    chat_id=chat_id,
                    user_id=user_id,
                ),
            )
            return True

        if user_id is None:
            self._logger.warning(
                "Unable to verify admin status: user_id is missing.",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    chat_id=chat_id,
                ),
            )
            return False

        normalized_chat_id = self._normalize_numeric_id(
            chat_id,
            request_id=correlation_id,
            operation=operation,
            field="chat_id",
        )
        normalized_user_id = self._normalize_numeric_id(
            user_id,
            request_id=correlation_id,
            operation=operation,
            field="user_id",
        )

        if normalized_chat_id is None or normalized_user_id is None:
            return False

        try:
            member = await self._bot.get_chat_member(
                chat_id=normalized_chat_id,
                user_id=normalized_user_id,
            )
        except TelegramError as error:
            self._logger.warning(
                "Failed to verify admin status",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    chat_id=chat_id,
                    user_id=user_id,
                    meta_error=sanitize_label(str(error)),
                ),
            )
            return False

        self._logger.debug(
            "ACL verification completed",
            extra=log_context(
                request_id=correlation_id,
                operation=operation,
                chat_id=chat_id,
                user_id=user_id,
                meta_member_status=member.status,
            ),
        )
        return member.status in {"administrator", "creator", "owner"}

    async def require_admin(
        self,
        *,
        chat_id: int | str,
        chat_type: str,
        user_id: int | str | None,
        on_denied: Callable[[str], Awaitable[None]],
        locale: str | None = None,
        request_id: str | None = None,
    ) -> bool:
        """Ensure the acting user has admin rights; send feedback if not."""
        correlation_id = request_id or new_request_id()
        operation = "acl.require_admin"
        if not self.is_group_context(chat_type):
            return True

        if user_id is None:
            await on_denied(
                translate(
                    "acl.missing_user",
                    locale=locale,
                    request_id=correlation_id,
                )
            )
            return False

        if await self.verify_admin(
            chat_id,
            user_id,
            chat_type,
            request_id=correlation_id,
        ):
            return True

        await on_denied(
            translate(
                "acl.admin_only",
                locale=locale,
                request_id=correlation_id,
            )
        )
        self._logger.debug(
            "ACL verification failed",
            extra=log_context(
                request_id=correlation_id,
                operation=operation,
                chat_id=chat_id,
                user_id=user_id,
                chat_type=chat_type,
            ),
        )
        return False
