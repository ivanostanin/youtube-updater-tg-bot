# YouTube Updater Telegram Bot

A Telegram bot that monitors YouTube channels and sends notifications when new videos are uploaded.

## Features

- Subscribe to YouTube channels, videos, or playlists
- Receive instant notifications for new video uploads
- Manage subscriptions with simple commands
- Support for various YouTube URL formats
- Webhook-based real-time notifications via PubSubHubbub

## Quick Start

1. **Clone and Setup**
   ```bash
   git clone <repository-url>
   cd youtube-updater-tg-bot
   source .venv/bin/activate
   uv pip install -e ".[dev]"
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Add your API keys to .env file 
   ```

3. **Get Required API Keys**
   - **Telegram Bot Token**: Create a bot via [@BotFather](https://t.me/botfather)
   - **YouTube API Key**: Get from [Google Cloud Console](https://console.cloud.google.com/)

4. **Run the Bot**
   ```bash
   python -m src.main
   ```

## Bot Commands

- `/start` - Start the bot and see welcome message
- `/subscribe <YouTube URL>` - Subscribe to a channel/video/playlist
- `/list` - Show your active subscriptions
- `/unsubscribe` - Remove subscriptions
- `/help` - Show available commands

## Supported YouTube URL Formats

- Channel by ID: `https://youtube.com/channel/CHANNEL_ID`
- Channel by handle: `https://youtube.com/@username`
- Video: `https://youtube.com/watch?v=VIDEO_ID`
- Short URL: `https://youtu.be/VIDEO_ID`
- Playlist: `https://youtube.com/playlist?list=PLAYLIST_ID`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather | Required |
| `YOUTUBE_API_KEY` | YouTube Data API v3 key | Required |
| `DATABASE_URL` | Database connection string | `sqlite+aiosqlite:///./bot.db` |
| `WEBHOOK_HOST` | Webhook server host | `localhost` |
| `WEBHOOK_PORT` | Webhook server port | `8000` |
| `LOG_LEVEL` | Logging level | `INFO` |

## Architecture

The bot consists of two main components:

1. **Telegram Bot**: Handles user interactions and commands
2. **Webhook Server**: Receives real-time notifications from YouTube via PubSubHubbub

When users subscribe to channels, the bot:
1. Validates the YouTube URL
2. Stores subscription in database
3. Registers for webhook notifications from YouTube
4. Sends notifications to users when new videos are uploaded

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if needed
5. Submit a pull request

## License

MIT License