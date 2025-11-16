# YouTube Updater Telegram Bot

[![CI](https://github.com/ivanostanin/youtube-updater-tg-bot/actions/workflows/main.yml/badge.svg?branch=master)](https://github.com/ivanostanin/youtube-updater-tg-bot/actions/workflows/main.yml)

A Telegram bot that monitors YouTube channels and sends notifications when new videos are uploaded.

## Features

- Subscribe to YouTube channels, videos, or playlists
- Receive instant notifications for new video uploads
- Manage subscriptions with simple commands
- Multilingual responses (English, Russian, German) with per-chat `/language` control
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
- `/language` - Select your preferred language for this chat
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
| `WEBHOOK_PATH` | Path for webhook endpoint | `/webhook/youtube` |
| `LOG_LEVEL` | Logging level (`DEBUG` enables structured tracing) | `INFO` |
| `DEFAULT_LOCALE` | Fallback locale for new chats (`en`, `ru`, `de`) | `en` |
| `PUBSUB_LEASE_RENEWAL_INTERVAL` | Seconds between lease renewal scans | `3600` |
| `PUBSUB_LEASE_RENEWAL_THRESHOLD` | Renew leases that expire within this window (seconds) | `21600` |
| `PUBSUB_LEASE_RENEWAL_BATCH_LIMIT` | Max channels processed per renewal run (`None` for unlimited) | `50` |

Telegram supplies `language_code` values like `en-US` or `es`. These are normalized to one of the supported catalogs (`en`, `ru`, `de`) and any unsupported code gracefully falls back to `DEFAULT_LOCALE`. Chat administrators can always run `/language` to pick English, Русский, or Deutsch via the inline selector if they want to override the automatic choice.

## Debugging Playbook

1. Set `LOG_LEVEL=DEBUG` in your `.env` (or export it in your shell) before launching the bot: `LOG_LEVEL=DEBUG uv run python -m src.main`.
2. Reproduce the issue; each handler, repository call, and webhook operation will now log `chat_id`, `chat_type`, `user_id`, `channel_id`, `subscription_id`, `video_id`, `operation`, and a `request_id`.
3. Track a single `request_id` across the logs to follow the full flow (Telegram command → DB operations → PubSub/Webhook/Notification).
4. Metadata prefixed with `meta_` (for example `meta_chat_title` or `meta_url_preview`) provides sanitized context without leaking private content.

## Architecture

The bot consists of two main components:

1. **Telegram Bot**: Handles user interactions and commands
2. **Webhook Server**: Receives real-time notifications from YouTube via PubSubHubbub

When users subscribe to channels, the bot:
1. Validates the YouTube URL
2. Stores subscription in database
3. Registers for webhook notifications from YouTube
4. Sends notifications to users when new videos are uploaded

## Test GitHub Actions Locally

Use [act](https://github.com/nektos/act) to dry-run the `CI` workflow without pushing commits.

1. Install prerequisites: Docker (running daemon) and the `act` CLI (`brew install act` on macOS or download from the releases page).
2. Ensure the provided `.actrc` is available so `ubuntu-latest` steps run inside the `catthehacker/ubuntu:full-latest` image (matches GitHub's runner environment).
3. Execute the workflow:
   ```bash
   # Simulate the pull_request trigger and run the tests job
   act pull_request -W .github/workflows/test.yml -j tests
   ```
   Use `-s VAR=value` or create an `.secrets` file if your workflow relies on secrets.

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if needed
5. Submit a pull request

## License

MIT License
