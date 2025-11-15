from urllib.parse import urlparse

import httpx

from ..utils.logging import get_logger, log_context, new_request_id, sanitize_label


logger = get_logger(__name__)


class PubSubManager:
    """Manager for YouTube PubSubHubbub subscriptions."""

    def __init__(self, webhook_url: str) -> None:
        self.webhook_url = webhook_url
        self.hub_url = "https://pubsubhubbub.appspot.com/subscribe"
        self.client = httpx.AsyncClient()
        self._local_callback = self._is_local_callback()

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    def _is_local_callback(self) -> bool:
        """Return True when webhook callback points to localhost/loopback."""
        parsed = urlparse(self.webhook_url)
        hostname = parsed.hostname or ""
        return hostname in {"localhost", "127.0.0.1", "0.0.0.0"} or hostname.startswith("127.")

    def _short_circuit(self, action: str, channel_id: str, *, request_id: str) -> bool:
        """Skip remote hub calls for local callbacks to avoid noisy failures."""
        if not self._local_callback:
            return False

        logger.info(
            "Skipping PubSub action because callback is local-only",
            extra=log_context(
                request_id=request_id,
                operation=f"pubsub.{action}",
                channel_id=channel_id,
                meta_webhook_url=self.webhook_url,
            ),
        )
        return True

    def get_topic_url(self, channel_id: str) -> str:
        """Get the topic URL for a YouTube channel."""
        return f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"

    async def subscribe_to_channel(self, channel_id: str) -> bool:
        """Subscribe to YouTube channel updates via PubSubHubbub."""
        request_id = new_request_id()
        operation = "pubsub.subscribe"
        try:
            if self._short_circuit("subscribe", channel_id, request_id=request_id):
                return True

            topic_url = self.get_topic_url(channel_id)

            data = {
                "hub.callback": self.webhook_url,
                "hub.topic": topic_url,
                "hub.verify": "sync",
                "hub.mode": "subscribe",
            }

            logger.debug(
                "Submitting PubSub subscribe request",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_payload={k: v for k, v in data.items() if "hub" in k},
                ),
            )

            response = await self.client.post(
                self.hub_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

            if response.status_code == 204:
                logger.info(
                    "Successfully subscribed to channel",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return True
            elif response.status_code == 409:
                logger.info(
                    "Channel already has an active subscription - treating as success",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return True
            else:
                logger.error(
                    "Failed to subscribe to channel",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                        meta_response_body=sanitize_label(response.text),
                    ),
                )
                return False

        except httpx.TimeoutException:
            logger.error(
                "Timeout while subscribing to channel - treating as success",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                ),
            )
            return True
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error subscribing to channel",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error subscribing to channel",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return False

    async def unsubscribe_from_channel(self, channel_id: str) -> bool:
        """Unsubscribe from YouTube channel updates."""
        request_id = new_request_id()
        operation = "pubsub.unsubscribe"
        try:
            if self._short_circuit("unsubscribe", channel_id, request_id=request_id):
                return True

            topic_url = self.get_topic_url(channel_id)

            data = {
                "hub.callback": self.webhook_url,
                "hub.topic": topic_url,
                "hub.verify": "sync",
                "hub.mode": "unsubscribe",
            }

            response = await self.client.post(
                self.hub_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

            if response.status_code == 204:
                logger.info(
                    "Successfully unsubscribed from channel",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return True
            elif response.status_code == 404:
                logger.info(
                    "Channel subscription not found - treating as success",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return True
            elif response.status_code == 409:
                logger.info(
                    "Unsubscription could not be verified (HTTP 409) - treating as success",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return True
            else:
                logger.error(
                    "Failed to unsubscribe from channel",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                        meta_response_body=sanitize_label(response.text),
                    ),
                )
                return False

        except httpx.TimeoutException:
            logger.error(
                "Timeout while unsubscribing from channel - treating as success",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                ),
            )
            return True
        except httpx.HTTPError as e:
            logger.error(
                "HTTP error unsubscribing from channel",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return False
        except Exception as e:
            logger.error(
                "Unexpected error unsubscribing from channel",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return False

    async def verify_subscription(self, channel_id: str) -> str | None:
        """Verify if subscription is active by checking the topic."""
        request_id = new_request_id()
        operation = "pubsub.verify"
        try:
            topic_url = self.get_topic_url(channel_id)
            response = await self.client.get(topic_url, timeout=10.0)

            if response.status_code == 200:
                logger.debug(
                    "Verified channel subscription via topic feed",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return response.text
            else:
                logger.warning(
                    "Could not verify subscription via topic feed",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_status_code=response.status_code,
                    ),
                )
                return None

        except Exception as e:
            logger.error(
                "Error verifying subscription via topic feed",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return None
