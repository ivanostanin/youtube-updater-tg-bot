"""Unit tests for PubSubHubbub webhook manager.

Tests cover webhook subscription, unsubscription, verification,
error handling, and retry logic.
"""

from unittest.mock import AsyncMock, MagicMock

import allure
import httpx
import pytest

from src.webhooks.pubsub import PubSubManager


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
def test_pubsub_manager_initialization():
    """Test PubSubManager initializes correctly with webhook URL.

    Args:
        None
    """
    webhook_url = "https://example.com/webhook/youtube"

    manager = PubSubManager(webhook_url)

    assert manager.webhook_url == webhook_url
    assert manager.hub_url == "https://pubsubhubbub.appspot.com/subscribe"
    assert manager.client is not None


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_get_topic_url():
    """Test topic URL generation for YouTube channel.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    topic_url = manager.get_topic_url("UCtest123")

    assert topic_url == "https://www.youtube.com/xml/feeds/videos.xml?channel_id=UCtest123"
    assert "channel_id=UCtest123" in topic_url


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscribe_to_channel_success():
    """Test successful channel subscription returns True.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock successful response (204 No Content)
    mock_response = MagicMock()
    mock_response.status_code = 204
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.subscribe_to_channel("UCtest123")

    assert result is True
    manager.client.post.assert_called_once()
    call_args = manager.client.post.call_args
    assert call_args[0][0] == manager.hub_url
    assert call_args[1]["data"]["hub.mode"] == "subscribe"
    assert "UCtest123" in call_args[1]["data"]["hub.topic"]


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscribe_to_channel_already_subscribed():
    """Test subscribing to already subscribed channel returns True.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock 409 Conflict response (already subscribed)
    mock_response = MagicMock()
    mock_response.status_code = 409
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.subscribe_to_channel("UCtest123")

    assert result is True


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_subscribe_to_channel_failure():
    """Test failed channel subscription returns False.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock error response (400 Bad Request)
    mock_response = MagicMock()
    mock_response.status_code = 400
    mock_response.text = "Bad Request"
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.subscribe_to_channel("UCtest123")

    assert result is False


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_subscribe_to_channel_timeout():
    """Test subscription timeout is handled gracefully.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock timeout exception
    manager.client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

    result = await manager.subscribe_to_channel("UCtest123")

    # Timeout is treated as success per implementation
    assert result is True


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_subscribe_to_channel_http_error():
    """Test subscription HTTP error is handled gracefully.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock HTTP error
    manager.client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=500)
        )
    )

    result = await manager.subscribe_to_channel("UCtest123")

    assert result is False


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_subscribe_to_channel_generic_exception():
    """Test subscription handles generic exceptions gracefully.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock generic exception
    manager.client.post = AsyncMock(side_effect=Exception("Unexpected error"))

    result = await manager.subscribe_to_channel("UCtest123")

    assert result is False


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_from_channel_success():
    """Test successful channel unsubscription returns True.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock successful response (204 No Content)
    mock_response = MagicMock()
    mock_response.status_code = 204
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.unsubscribe_from_channel("UCtest123")

    assert result is True
    manager.client.post.assert_called_once()
    call_args = manager.client.post.call_args
    assert call_args[1]["data"]["hub.mode"] == "unsubscribe"


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_from_channel_not_found():
    """Test unsubscribing from non-existent subscription returns True.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock 404 Not Found response
    mock_response = MagicMock()
    mock_response.status_code = 404
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.unsubscribe_from_channel("UCtest123")

    # Not found is treated as success per implementation
    assert result is True


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_unsubscribe_from_channel_failure():
    """Test failed channel unsubscription returns False.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock error response (500 Server Error)
    mock_response = MagicMock()
    mock_response.status_code = 500
    mock_response.text = "Server Error"
    manager.client.post = AsyncMock(return_value=mock_response)

    result = await manager.unsubscribe_from_channel("UCtest123")

    assert result is False


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_unsubscribe_from_channel_timeout():
    """Test unsubscription timeout is handled gracefully.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock timeout exception
    manager.client.post = AsyncMock(side_effect=httpx.TimeoutException("Request timeout"))

    result = await manager.unsubscribe_from_channel("UCtest123")

    # Timeout is treated as success per implementation
    assert result is True


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_unsubscribe_from_channel_http_error():
    """Test unsubscription HTTP error is handled gracefully.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock HTTP error
    manager.client.post = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "Server Error", request=MagicMock(), response=MagicMock(status_code=503)
        )
    )

    result = await manager.unsubscribe_from_channel("UCtest123")

    assert result is False


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_verify_subscription_success():
    """Test verifying subscription returns feed content.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock successful response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = '<?xml version="1.0"?><feed>...</feed>'
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.verify_subscription("UCtest123")

    assert result is not None
    assert "<feed>" in result
    manager.client.get.assert_called_once()


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_verify_subscription_not_found():
    """Test verifying non-existent subscription returns None.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock 404 response
    mock_response = MagicMock()
    mock_response.status_code = 404
    manager.client.get = AsyncMock(return_value=mock_response)

    result = await manager.verify_subscription("UCtest123")

    assert result is None


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_verify_subscription_exception():
    """Test verifying subscription handles exceptions gracefully.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")

    # Mock exception
    manager.client.get = AsyncMock(side_effect=Exception("Network error"))

    result = await manager.verify_subscription("UCtest123")

    assert result is None


@allure.feature("Webhooks")
@allure.story("PubSubHubbub")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_close_client():
    """Test closing HTTP client works correctly.

    Args:
        None
    """
    manager = PubSubManager("https://example.com/webhook")
    manager.client.aclose = AsyncMock()

    await manager.close()

    manager.client.aclose.assert_called_once()
