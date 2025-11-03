"""Unit tests for YouTube API client.

Tests cover channel info extraction, video URL parsing, API calls,
error handling, and feed checking functionality.
"""

from unittest.mock import AsyncMock, MagicMock

import allure
import httpx
import pytest

from src.youtube.api import YouTubeAPI


@allure.feature("YouTube API")
@allure.story("Channel Discovery")
@allure.severity(allure.severity_level.BLOCKER)
@pytest.mark.unit
def test_extract_channel_id_from_channel_url():
    """Test extracting channel ID from standard channel URL.

    Args:
        None
    """
    api = YouTubeAPI()

    channel_id = api.extract_channel_id("https://www.youtube.com/channel/UCtest123")

    assert channel_id == "UCtest123"


@allure.feature("YouTube API")
@allure.story("Channel Discovery")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_extract_channel_id_from_handle_url():
    """Test extracting channel ID from @handle URL format.

    Args:
        None
    """
    api = YouTubeAPI()

    channel_id = api.extract_channel_id("https://www.youtube.com/@testchannel")

    assert channel_id == "testchannel"


@allure.feature("YouTube API")
@allure.story("Channel Discovery")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_extract_channel_id_from_custom_url():
    """Test extracting channel ID from custom URL format.

    Args:
        None
    """
    api = YouTubeAPI()

    channel_id = api.extract_channel_id("https://www.youtube.com/c/testchannel")

    assert channel_id == "testchannel"


@allure.feature("YouTube API")
@allure.story("Channel Discovery")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_extract_channel_id_from_user_url():
    """Test extracting channel ID from user URL format.

    Args:
        None
    """
    api = YouTubeAPI()

    channel_id = api.extract_channel_id("https://www.youtube.com/user/testchannel")

    assert channel_id == "testchannel"


@allure.feature("YouTube API")
@allure.story("Channel Discovery")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_extract_channel_id_invalid_url():
    """Test extracting channel ID from invalid URL returns None.

    Args:
        None
    """
    api = YouTubeAPI()

    channel_id = api.extract_channel_id("https://www.google.com")

    assert channel_id is None


@allure.feature("YouTube API")
@allure.story("Video Discovery")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_extract_video_id_from_watch_url():
    """Test extracting video ID from standard watch URL.

    Args:
        None
    """
    api = YouTubeAPI()

    video_id = api.extract_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ")

    assert video_id == "dQw4w9WgXcQ"


@allure.feature("YouTube API")
@allure.story("Video Discovery")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_extract_video_id_from_short_url():
    """Test extracting video ID from youtu.be short URL.

    Args:
        None
    """
    api = YouTubeAPI()

    video_id = api.extract_video_id("https://youtu.be/dQw4w9WgXcQ")

    assert video_id == "dQw4w9WgXcQ"


@allure.feature("YouTube API")
@allure.story("Video Discovery")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
def test_extract_video_id_from_embed_url():
    """Test extracting video ID from embed URL format.

    Args:
        None
    """
    api = YouTubeAPI()

    video_id = api.extract_video_id("https://www.youtube.com/embed/dQw4w9WgXcQ")

    assert video_id == "dQw4w9WgXcQ"


@allure.feature("YouTube API")
@allure.story("Video Discovery")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_extract_video_id_invalid_url():
    """Test extracting video ID from invalid URL returns None.

    Args:
        None
    """
    api = YouTubeAPI()

    video_id = api.extract_video_id("https://www.google.com")

    assert video_id is None


@allure.feature("YouTube API")
@allure.story("Playlist Discovery")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_extract_playlist_id():
    """Test extracting playlist ID from playlist URL.

    Args:
        None
    """
    api = YouTubeAPI()

    playlist_id = api.extract_playlist_id("https://www.youtube.com/playlist?list=PLtest123")

    assert playlist_id == "PLtest123"


@allure.feature("YouTube API")
@allure.story("Playlist Discovery")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_extract_playlist_id_invalid_url():
    """Test extracting playlist ID from invalid URL returns None.

    Args:
        None
    """
    api = YouTubeAPI()

    playlist_id = api.extract_playlist_id("https://www.google.com")

    assert playlist_id is None


@allure.feature("YouTube API")
@allure.story("Channel API Calls")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_get_channel_by_id_success(mock_httpx_client):
    """Test getting channel info by ID returns channel data.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "items": [
                {
                    "id": "UCtest123",
                    "snippet": {
                        "title": "Test Channel",
                        "description": "Test Description",
                        "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                    },
                }
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = await api.get_channel_by_id("UCtest123")

    assert result is not None
    assert result["id"] == "UCtest123"
    assert result["title"] == "Test Channel"
    assert result["url"] == "https://www.youtube.com/channel/UCtest123"
    mock_httpx_client.get.assert_called_once()


@allure.feature("YouTube API")
@allure.story("Channel API Calls")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_get_channel_by_id_not_found(mock_httpx_client):
    """Test getting channel info by ID returns None when not found.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock empty API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(return_value={"items": []})
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = await api.get_channel_by_id("UCnonexistent")

    assert result is None


@allure.feature("YouTube API")
@allure.story("Channel API Calls")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_get_channel_by_id_api_error(mock_httpx_client):
    """Test getting channel info handles API errors gracefully.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock API error
    mock_httpx_client.get = AsyncMock(
        side_effect=httpx.HTTPStatusError(
            "API Error", request=MagicMock(), response=MagicMock(status_code=403)
        )
    )

    result = await api.get_channel_by_id("UCtest123")

    assert result is None


@allure.feature("YouTube API")
@allure.story("Channel API Calls")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_get_channel_by_handle_success(mock_httpx_client):
    """Test getting channel info by handle returns channel data.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "items": [
                {
                    "id": "UCtest123",
                    "snippet": {
                        "title": "Test Channel",
                        "description": "Test Description",
                        "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                    },
                }
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = await api.get_channel_by_handle("@testchannel")

    assert result is not None
    assert result["id"] == "UCtest123"
    assert result["title"] == "Test Channel"


@allure.feature("YouTube API")
@allure.story("Video API Calls")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_get_video_info_success(mock_httpx_client):
    """Test getting video info returns video data.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock successful API response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = MagicMock(
        return_value={
            "items": [
                {
                    "id": "dQw4w9WgXcQ",
                    "snippet": {
                        "title": "Test Video",
                        "description": "Test video description",
                        "channelId": "UCtest123",
                        "channelTitle": "Test Channel",
                        "publishedAt": "2024-01-01T00:00:00Z",
                        "thumbnails": {"default": {"url": "https://example.com/thumb.jpg"}},
                    },
                }
            ]
        }
    )
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    result = await api.get_video_info("dQw4w9WgXcQ")

    assert result is not None
    assert result["id"] == "dQw4w9WgXcQ"
    assert result["title"] == "Test Video"
    assert result["channel_id"] == "UCtest123"
    assert result["url"] == "https://www.youtube.com/watch?v=dQw4w9WgXcQ"


@allure.feature("YouTube API")
@allure.story("URL Resolution")
@allure.severity(allure.severity_level.CRITICAL)
@pytest.mark.unit
async def test_resolve_url_playlist(mock_httpx_client):
    """Test resolving playlist URL returns playlist info.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    result = await api.resolve_url("https://www.youtube.com/playlist?list=PLtest123")

    assert result is not None
    assert result["type"] == "playlist"
    assert result["id"] == "PLtest123"


@allure.feature("YouTube API")
@allure.story("Feed Management")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
def test_get_feed_url():
    """Test generating RSS feed URL for channel.

    Args:
        None
    """
    api = YouTubeAPI()

    feed_url = api.get_feed_url("UCtest123")

    assert feed_url == "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123"


@allure.feature("YouTube API")
@allure.story("Feed Management")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_check_feed_for_updates_success(mock_httpx_client):
    """Test checking RSS feed returns video list.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock RSS feed response
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.text = """<?xml version="1.0" encoding="UTF-8"?>
    <feed xmlns:yt="http://www.youtube.com/xml/schemas/2015">
        <entry>
            <yt:videoId>dQw4w9WgXcQ</yt:videoId>
            <yt:channelId>UCtest123</yt:channelId>
            <title>Test Video</title>
            <summary>Test Description</summary>
            <link href="https://www.youtube.com/watch?v=dQw4w9WgXcQ" />
            <published>2024-01-01T00:00:00+00:00</published>
        </entry>
    </feed>"""
    mock_response.raise_for_status = MagicMock()
    mock_httpx_client.get = AsyncMock(return_value=mock_response)

    videos = await api.check_feed_for_updates(
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123"
    )

    assert len(videos) == 1
    assert videos[0]["id"] == "dQw4w9WgXcQ"
    assert videos[0]["title"] == "Test Video"


@allure.feature("YouTube API")
@allure.story("Feed Management")
@allure.severity(allure.severity_level.NORMAL)
@pytest.mark.unit
async def test_check_feed_for_updates_error(mock_httpx_client):
    """Test checking RSS feed handles errors gracefully.

    Args:
        mock_httpx_client: Mock httpx client fixture.
    """
    api = YouTubeAPI()
    api.client = mock_httpx_client

    # Mock network error
    mock_httpx_client.get = AsyncMock(side_effect=httpx.NetworkError("Connection failed"))

    videos = await api.check_feed_for_updates(
        "https://www.youtube.com/feeds/videos.xml?channel_id=UCtest123"
    )

    assert videos == []
