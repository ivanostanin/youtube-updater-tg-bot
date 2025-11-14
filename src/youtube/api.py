import logging
import re
from typing import Any

import feedparser
import httpx

from ..utils.config import settings


logger = logging.getLogger(__name__)


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
        # Handle different YouTube URL formats
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
                # For @handle format, we need to resolve it via API
                if "@" in url:
                    return identifier  # Will be resolved later
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

    async def get_channel_by_id(self, channel_id: str) -> dict[str, Any] | None:
        """Get channel information by channel ID."""
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
                return {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
        except Exception as e:
            logger.error(f"Error fetching channel {channel_id}: {e}")

        return None

    async def get_channel_by_username(self, username: str) -> dict[str, Any] | None:
        """Get channel information by username."""
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
                return {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
        except Exception as e:
            logger.error(f"Error fetching channel by username {username}: {e}")

        return None

    async def get_channel_by_handle(self, handle: str) -> dict[str, Any] | None:
        """Get channel information by handle (@username)."""
        try:
            # Remove @ if present
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
                return {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "url": f"https://www.youtube.com/channel/{item['id']}",
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                }
        except Exception as e:
            logger.error(f"Error fetching channel by handle {handle}: {e}")

        return None

    async def get_video_info(self, video_id: str) -> dict[str, Any] | None:
        """Get video information by video ID."""
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
                return {
                    "id": item["id"],
                    "title": item["snippet"]["title"],
                    "description": item["snippet"]["description"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_title": item["snippet"]["channelTitle"],
                    "published_at": item["snippet"]["publishedAt"],
                    "thumbnail": item["snippet"]["thumbnails"]["default"]["url"],
                    "url": f"https://www.youtube.com/watch?v={item['id']}",
                }
        except Exception as e:
            logger.error(f"Error fetching video {video_id}: {e}")

        return None

    async def resolve_url(self, url: str) -> dict[str, Any] | None:
        """Resolve YouTube URL and return appropriate information."""
        # Try to extract channel ID
        channel_id = self.extract_channel_id(url)
        if channel_id:
            # Check if it's a handle
            if "@" in url:
                return await self.get_channel_by_handle(channel_id)
            else:
                channel_info = await self.get_channel_by_id(channel_id)
                if not channel_info:
                    # Try as username
                    channel_info = await self.get_channel_by_username(channel_id)
                return channel_info

        # Try to extract video ID
        video_id = self.extract_video_id(url)
        if video_id:
            video_info = await self.get_video_info(video_id)
            if video_info:
                # Also get channel info for the video
                channel_info = await self.get_channel_by_id(video_info["channel_id"])
                if channel_info:
                    return {
                        "type": "video",
                        "video": video_info,
                        "channel": channel_info,
                    }

        # Try to extract playlist ID
        playlist_id = self.extract_playlist_id(url)
        if playlist_id:
            # For now, just return playlist info
            return {
                "type": "playlist",
                "id": playlist_id,
                "url": url,
            }

        return None

    def get_feed_url(self, channel_id: str) -> str:
        """Get RSS feed URL for a YouTube channel."""
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"

    async def check_feed_for_updates(self, feed_url: str) -> list[dict[str, Any]]:
        """Check RSS feed for new videos."""
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

            return videos

        except Exception as e:
            logger.error(f"Error checking feed {feed_url}: {e}")
            return []
