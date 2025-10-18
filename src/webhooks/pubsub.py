import logging

import httpx


logger = logging.getLogger(__name__)


class PubSubManager:
    """Manager for YouTube PubSubHubbub subscriptions."""

    def __init__(self, webhook_url: str):
        self.webhook_url = webhook_url
        self.hub_url = "https://pubsubhubbub.appspot.com/subscribe"
        self.client = httpx.AsyncClient()

    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()

    def get_topic_url(self, channel_id: str) -> str:
        """Get the topic URL for a YouTube channel."""
        return f"https://www.youtube.com/xml/feeds/videos.xml?channel_id={channel_id}"

    async def subscribe_to_channel(self, channel_id: str) -> bool:
        """Subscribe to YouTube channel updates via PubSubHubbub."""
        try:
            topic_url = self.get_topic_url(channel_id)

            data = {
                "hub.callback": self.webhook_url,
                "hub.topic": topic_url,
                "hub.verify": "sync",
                "hub.mode": "subscribe",
            }

            logger.info(data)

            response = await self.client.post(
                self.hub_url,
                data=data,
                headers={"Content-Type": "application/x-www-form-urlencoded"},
                timeout=30.0,
            )

            if response.status_code == 204:
                logger.info(f"Successfully subscribed to channel {channel_id}")
                return True
            elif response.status_code == 409:
                logger.info(
                    f"Channel {channel_id} already has an active subscription - treating as success"
                )
                return True
            else:
                logger.error(
                    f"Failed to subscribe to channel {channel_id}: {response.status_code} - {response.text}"
                )
                return False

        except httpx.TimeoutException:
            logger.error(f"Timeout while subscribing to channel {channel_id} - treating as success")
            return True
        except httpx.HTTPError as e:
            logger.error(f"HTTP error subscribing to channel {channel_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error subscribing to channel {channel_id}: {e}")
            return False

    async def unsubscribe_from_channel(self, channel_id: str) -> bool:
        """Unsubscribe from YouTube channel updates."""
        try:
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
                logger.info(f"Successfully unsubscribed from channel {channel_id}")
                return True
            elif response.status_code == 404:
                logger.info(f"Channel {channel_id} subscription not found - treating as success")
                return True
            else:
                logger.error(
                    f"Failed to unsubscribe from channel {channel_id}: {response.status_code} - {response.text}"
                )
                return False

        except httpx.TimeoutException:
            logger.error(
                f"Timeout while unsubscribing from channel {channel_id} - treating as success"
            )
            return True
        except httpx.HTTPError as e:
            logger.error(f"HTTP error unsubscribing from channel {channel_id}: {e}")
            return False
        except Exception as e:
            logger.error(f"Error unsubscribing from channel {channel_id}: {e}")
            return False

    async def verify_subscription(self, channel_id: str) -> str | None:
        """Verify if subscription is active by checking the topic."""
        try:
            topic_url = self.get_topic_url(channel_id)
            response = await self.client.get(topic_url, timeout=10.0)

            if response.status_code == 200:
                return response.text
            else:
                logger.warning(
                    f"Could not verify subscription for channel {channel_id}: {response.status_code}"
                )
                return None

        except Exception as e:
            logger.error(f"Error verifying subscription for channel {channel_id}: {e}")
            return None
