"""Unit tests for ACLService behaviour."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import allure
import pytest
from telegram.error import TelegramError

from src.services import ACLService


@allure.feature("Services")
@allure.story("ACL")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_verify_admin_private_chat_skips_lookup():
    """Private chats do not invoke Telegram API for admin checks."""
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock()
    service = ACLService(bot)

    result = await service.verify_admin(chat_id="123", user_id="456", chat_type="private")

    assert result is True
    bot.get_chat_member.assert_not_called()


@allure.feature("Services")
@allure.story("ACL")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_verify_admin_allows_administrators():
    """Administrators are authorised for group operations."""
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="administrator"))
    service = ACLService(bot)

    result = await service.verify_admin(chat_id="-1000", user_id="42", chat_type="supergroup")

    assert result is True
    bot.get_chat_member.assert_awaited_once()


@allure.feature("Services")
@allure.story("ACL")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_verify_admin_handles_non_admin_status():
    """Non-admin members must be rejected."""
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="member"))
    service = ACLService(bot)

    result = await service.verify_admin(chat_id="-1000", user_id="42", chat_type="group")

    assert result is False
    bot.get_chat_member.assert_awaited_once()


@allure.feature("Services")
@allure.story("ACL")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_require_admin_reports_denial_message():
    """require_admin notifies callers when access is denied."""
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(return_value=SimpleNamespace(status="member"))
    service = ACLService(bot)

    messages: list[str] = []

    async def capture(text: str) -> None:
        messages.append(text)

    allowed = await service.require_admin(
        chat_id="-1000",
        chat_type="supergroup",
        user_id="42",
        on_denied=capture,
    )

    assert allowed is False
    assert messages == ["Only chat administrators can manage subscriptions here."]


@allure.feature("Services")
@allure.story("ACL")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_verify_admin_handles_telegram_error():
    """Telegram API failures should not crash the service."""
    bot = AsyncMock()
    bot.get_chat_member = AsyncMock(side_effect=TelegramError("forbidden"))
    service = ACLService(bot)

    result = await service.verify_admin(chat_id="-1000", user_id="42", chat_type="group")

    assert result is False
    bot.get_chat_member.assert_awaited_once()
