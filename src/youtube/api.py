import re
from typing import Any

import feedparser
import httpx

from ..utils.config import settings
from ..utils.logging import get_logger, log_context, new_request_id, sanitize_label


logger = get_logger(__name__)


class YouTubeAPI:
    """YouTube API client for fetching channel and video information."""

    def __init__(self) -> None:
        self.api_key = settings.youtube_api_key
        self.base_url = "https://www.googleapis.com/youtube/v3"
        self.client = httpx.AsyncClient()

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    def extract_channel_id(self, url: str) -> str | None:
        """Extract channel ID from various YouTube URL formats."""
        patterns = [
            r"youtube\.com/channel/([a-zA-Z0-9_-]+)",
            r"youtube\.com/c/([a-zA-Z0-9_-]+)",
            r"youtube\.com/user/([a-zA-Z0-9_-]+)",
            r"youtube\.com/@([a-zA-Z0-9_.-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                identifier = match.group(1)
                if "@" in url:
                    return identifier  # Will be resolved via API later
                return identifier

        return None

    def extract_video_id(self, url: str) -> str | None:
        """Extract video ID from YouTube video URL."""
        patterns = [
            r"youtube\.com/watch\?v=([a-zA-Z0-9_-]+)",
            r"youtu\.be/([a-zA-Z0-9_-]+)",
            r"youtube\.com/embed/([a-zA-Z0-9_-]+)",
        ]

        for pattern in patterns:
            match = re.search(pattern, url)
            if match:
                return match.group(1)

        return None

    def extract_playlist_id(self, url: str) -> str | None:
        """Extract playlist ID from YouTube playlist URL."""
        pattern = r"youtube\.com/playlist\?list=([a-zA-Z0-9_-]+)"
        match = re.search(pattern, url)
        if match:
            return match.group(1)
        return None

    async def get_channel_by_id(
        self, channel_id: str, *, request_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get channel information by channel ID."""
        correlation_id = request_id or new_request_id()
        operation = "youtube.get_channel_by_id"
        try:
            response = await self.client.get(
                f"{self.base_url}/channels",
                params={
                    "key": self.api_key,
                    "id": channel_id,
                    "part": "snippet,contentDetails",
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("items"):
                item = data["items"][0]
                channel_data = {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
                logger.debug(
                    "Fetched channel by id",
                    extra=log_context(
                        request_id=correlation_id,
                        operation=operation,
                        channel_id=channel_id,
                        meta_channel_title=sanitize_label(item["snippet"]["title"]),
                    ),
                )
                return channel_data
        except Exception as e:
            logger.error(
                "Error fetching channel by id",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    channel_id=channel_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )

        return None

    async def get_channel_by_username(
        self, username: str, *, request_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get channel information by username."""
        correlation_id = request_id or new_request_id()
        operation = "youtube.get_channel_by_username"
        try:
            response = await self.client.get(
                f"{self.base_url}/channels",
                params={
                    "key": self.api_key,
                    "forUsername": username,
                    "part": "snippet,contentDetails",
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("items"):
                item = data["items"][0]
                channel_data = {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
                logger.debug(
                    "Fetched channel by username",
                    extra=log_context(
                        request_id=correlation_id,
                        operation=operation,
                        channel_id=item["id"],
                        meta_username=sanitize_label(username),
                        meta_channel_title=sanitize_label(item["snippet"]["title"]),
                    ),
                )
                return channel_data
        except Exception as e:
            logger.error(
                "Error fetching channel by username",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    meta_username=sanitize_label(username),
                    meta_error=sanitize_label(str(e)),
                ),
            )

        return None

    async def get_channel_by_handle(
        self, handle: str, *, request_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get channel information by handle (@username)."""
        correlation_id = request_id or new_request_id()
        operation = "youtube.get_channel_by_handle"
        try:
            handle = handle.lstrip("@")
            response = await self.client.get(
                f"{self.base_url}/channels",
                params={
                    "key": self.api_key,
                    "forHandle": f"@{handle}",
                    "part": "snippet,contentDetails",
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("items"):
                item = data["items"][0]
                channel_data = {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
                logger.debug(
                    "Fetched channel by handle",
                    extra=log_context(
                        request_id=correlation_id,
                        operation=operation,
                        channel_id=item["id"],
                        meta_handle=sanitize_label(handle),
                        meta_channel_title=sanitize_label(item["snippet"]["title"]),
                    ),
                )
                return channel_data
        except Exception as e:
            logger.error(
                "Error fetching channel by handle",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    meta_handle=sanitize_label(handle),
                    meta_error=sanitize_label(str(e)),
                ),
            )

        return None

    async def get_video_info(
        self, video_id: str, *, request_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get video information by video ID."""
        correlation_id = request_id or new_request_id()
        operation = "youtube.get_video_info"
        try:
            response = await self.client.get(
                f"{self.base_url}/videos",
                params={
                    "key": self.api_key,
                    "id": video_id,
                    "part": "snippet",
                },
            )
            response.raise_for_status()
            data = response.json()

            if data.get("items"):
                item = data["items"][0]
                video_data = {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "published_at": item["snippet"]["publishedAt"],
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
                logger.debug(
                    "Fetched video info",
                    extra=log_context(
                        request_id=correlation_id,
                        operation=operation,
                        video_id=video_id,
                        channel_id=item["snippet"]["channelId"],
                        meta_video_title=sanitize_label(item["snippet"]["title"]),
                    ),
                )
                return video_data
        except Exception as e:
            logger.error(
                "Error fetching video info",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    video_id=video_id,
                    meta_error=sanitize_label(str(e)),
                ),
            )

        return None

    async def resolve_url(
        self, url: str, *, request_id: str | None = None
    ) -> dict[str, Any] | None:
        """Resolve YouTube URL and return appropriate information."""
        correlation_id = request_id or new_request_id()
        logger.debug(
            "Resolving YouTube URL",
            extra=log_context(
                request_id=correlation_id,
                operation="youtube.resolve_url",
                meta_url_preview=sanitize_label(url),
            ),
        )

        channel_id = self.extract_channel_id(url)
        if channel_id:
            if "@" in url:
                return await self.get_channel_by_handle(
                    channel_id, request_id=correlation_id
                )
            channel_info = await self.get_channel_by_id(
                channel_id, request_id=correlation_id
            )
            if not channel_info:
                channel_info = await self.get_channel_by_username(
                    channel_id, request_id=correlation_id
                )
            return channel_info

        video_id = self.extract_video_id(url)
        if video_id:
            video_info = await self.get_video_info(video_id, request_id=correlation_id)
            if video_info:
                channel_info = await self.get_channel_by_id(
                    video_info["channel_id"], request_id=correlation_id
                )
                if channel_info:
                    return {
                        "type": "video",
                        "video": video_info,
                        "channel": channel_info,
                    }

        playlist_id = self.extract_playlist_id(url)
        if playlist_id:
            return {
                "type": "playlist",
                "id": playlist_id,
                "url": url,
            }

        logger.debug(
            "Unable to resolve YouTube URL",
            extra=log_context(
                request_id=correlation_id,
                operation="youtube.resolve_url",
                meta_url_preview=sanitize_label(url),
            ),
        )
        return None

    def get_feed_url(self, channel_id: str) -> str:
        """Get RSS feed URL for a YouTube channel."""
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    async def check_feed_for_updates(
        self, feed_url: str, *, request_id: str | None = None
    ) -> list[dict[str, Any]]:
        """Check RSS feed for new videos."""
        correlation_id = request_id or new_request_id()
        operation = "youtube.check_feed"
        try:
            response = await self.client.get(feed_url)
            response.raise_for_status()

            feed = feedparser.parse(response.text)
            videos = []

            for entry in feed.entries:
                video = {
                    "id": entry.yt_videoid,
                    "title": entry.title,
                    "description": entry.summary,
                    "url": entry.link,
                    "published_at": entry.published,
                    "channel_id": entry.yt_channelid,
                }
                videos.append(video)

            logger.debug(
                "Fetched feed entries",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    meta_feed_url=sanitize_label(feed_url),
                    meta_entry_count=len(videos),
                ),
            )
            return videos

        except Exception as e:
            logger.error(
                "Error checking YouTube feed",
                extra=log_context(
                    request_id=correlation_id,
                    operation=operation,
                    meta_feed_url=sanitize_label(feed_url),
                    meta_error=sanitize_label(str(e)),
                ),
            )
            return []
