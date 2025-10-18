# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Telegram bot that provides YouTube channel updates. The bot monitors watched YouTube channels and posts new video notifications to Telegram via direct messages, groups, or channels.

## Tech Stack

- **Language & Tools**: Python, uv (package manager), pytest (testing)
- **Database**: SQLAlchemy (async), SQLite (with possible PostgreSQL migration)
- **HTTP**: starlette, python-telegram-bot
- **Notifications**: Push notifications via https://pubsubhubbub.appspot.com/subscribe

## Development Environment

- **Python Version**: Python 3.13 (based on .venv structure)
- **Package Manager**: uv (preferred) or pip
- **Virtual Environment**: Located in `.venv/` directory
- **IDE**: PyCharm (configuration in `.idea/` directory)

## Common Commands

### Development Setup
```bash
# Activate virtual environment
source .venv/bin/activate

# Install dependencies (using uv - preferred)
uv pip install -e ".[dev]"

# Install dependencies (fallback to pip)
pip install -e ".[dev]"
```

### Running the Bot
```bash
# Run the bot
python -m src.main

# Or using the installed script (after pip install -e .)
youtube-updater-tg-bot
```

### Testing & Code Quality
```bash
# Run tests
pytest

# Run tests with Allure reporting
pytest --alluredir=allure-results

# Code formatting and linting (ruff)
ruff check src/ tests/
ruff check --fix src/ tests/
ruff format src/ tests/

# Type checking
mypy src/

# Pre-commit hooks (after installing dev dependencies)
pre-commit install
pre-commit run --all-files
```

### Docker Commands
```bash
# Build Docker image locally
./scripts/docker-build.sh

# Build with specific tag
./scripts/docker-build.sh -t v1.0.0

# Build for specific platform
./scripts/docker-build.sh -p linux/amd64

# Build and push to registry
./scripts/docker-build.sh --push -t latest

# Push existing image to Docker Hub
./scripts/docker-push.sh -u your-username

# Push with environment variables
export DOCKERHUB_USERNAME=your-username
export DOCKERHUB_TOKEN=your-token
./scripts/docker-push.sh

# Run container locally
./scripts/docker-run.sh

# Run in background
./scripts/docker-run.sh -d

# Run with custom port
./scripts/docker-run.sh -p 9000
```

### Project Management
```bash
# Build the package
python -m build

# Install in development mode
pip install -e .

# Deactivate virtual environment
deactivate
```

## Architecture & Features

### Core Features
- **Multi-platform support**: Personal messages, Telegram channels, and groups
- **ACL (Access Control)**: Users must be admin in groups/channels to configure bot
- **Webhook management**: Automated registration/unregistration with PubSubHubbub
- **Update logging**: Track and store updates for watched channels
- **Stateless design**: External DBMS or regular SQLite backups to S3 with restore on startup

### User Stories
- Subscribe to YouTube channels/videos/playlists and receive update notifications
- View update history with filtering by channel (customizable)
- Set auto-deletion timers for messages (1-7 days)
- Manage watched YouTube channels per user/group/channel
- **Premium features**:
  - LLM-powered video transcription summaries (cached, rate-limited by tokens)
  - Voice message narration of summaries

### Project Structure
```
├── src/
│   ├── bot/              # Telegram bot logic
│   ├── youtube/          # YouTube API integration
│   ├── database/         # SQLAlchemy models and migrations
│   ├── webhooks/         # PubSubHubbub webhook handling
│   ├── premium/          # LLM and voice features
│   └── utils/            # Shared utilities and helpers
├── tests/                # Unit and integration tests
├── scripts/              # Project scripts
├── deployment/           # Deployment configuration
│   ├── docker/           # Docker configuration
│   └── helm/             # Helm chart
└── .github/              # GitHub Actions workflows
```

## Deployment

- **Repository**: GitHub
- **CI/CD**: GitHub Actions for build and deploy
- **Container Registry**: Docker Hub
- **Infrastructure**: OCI Kubernetes cluster
- **Database**: SQLite with S3 backup strategy or PostgreSQL

### Kubernetes Deployment with Helm

```bash
# Install from local chart
helm install youtube-bot deployment/helm/youtube-updater-tg-bot \
  --set bot.telegramBotToken="your-bot-token" \
  --set bot.youtubeApiKey="your-api-key"

# Install with custom values file
helm install youtube-updater-tg-bot deployment/helm/youtube-updater-tg-bot -f my-values.yaml

# Using existing PVC
helm install youtube-updater-tg-bot deployment/helm/youtube-updater-tg-bot \
  --set persistence.existingClaim="my-pvc" \
  --set persistence.create=false

# With external secrets
helm install youtube-updater-tg-bot deployment/helm/youtube-updater-tg-bot \
  --set externalSecrets.enabled=true \
  --set externalSecrets.secretStore.name="vault-backend"

# With ingress enabled
helm install youtube-updater-tg-bot deployment/helm/youtube-updater-tg-bot \
  --set ingress.enabled=true \
  --set ingress.hosts[0].host="youtube-updater-tg-bot.example.com"

# Upgrade deployment
helm upgrade youtube-updater-tg-bot deployment/helm/youtube-updater-tg-bot

# Uninstall
helm uninstall youtube-updater-tg-bot
```

## Testing

- **Framework**: pytest
- **Types**: Unit tests and integration tests
- **Reporting**: Allure reports
- **Coverage**: Aim for comprehensive test coverage

## Package Management

This project uses `pyproject.toml` for modern Python package management:

### Installation Options
```bash
# Development installation with all dev dependencies
pip install -e ".[dev]"

# Production installation (core dependencies only)
pip install -e .

# From PyPI (when published)
pip install youtube-updater-tg-bot
```

### Dependencies
- **Core**: python-telegram-bot, starlette, uvicorn, SQLAlchemy, httpx, pydantic
- **Dev**: pytest, ruff, mypy, pre-commit, allure-pytest

### Configuration Files
- `pyproject.toml` - Main project configuration and dependencies
- `requirements.txt` - Legacy dependency file (maintained for compatibility)
- `.env.example` - Environment variables template

## Development Notes

- The project uses modern Python packaging with `pyproject.toml`
- Prefer `uv` over `pip` for package management when available
- Development dependencies are in the `[dev]` optional group
- Code quality tools are configured in `pyproject.toml`:
  - ruff for linting and formatting (line length: 100)
  - mypy for type checking
  - pytest for testing with async support
- Focus on async/await patterns for HTTP and database operations
- Comprehensive logging throughout the application
- Pre-commit hooks available for code quality enforcement