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

# Generate local Allure HTML report
allure generate allure-results --clean -o allure-report

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

### CI/CD
- GitHub Actions workflow `CI` (`.github/workflows/main.yml`) runs on pushes to `master` and on every pull request. It executes `ruff check`, `mypy`, and `pytest --alluredir=allure-results --cov=src` so failures block merges; configure a branch protection rule on `master` that requires the `CI` check.
- Successful workflow runs publish Allure HTML reports to GitHub Pages at `https://ivanostanin.github.io/youtube-updater-tg-bot/allure-latest/`. Raw `allure-results` artifacts (30-day retention) and `coverage.xml` are uploaded with each run for traceability and future badge automation.
- For troubleshooting, download the `allure-report` artifact from the workflow run or regenerate locally using the commands above; publishing to Pages occurs only on successful pushes to `master`.
- To test the workflow locally, install [act](https://github.com/nektos/act) plus Docker, rely on the checked-in `.actrc` (maps `ubuntu-latest` to `catthehacker/ubuntu:act-latest`), and run `act pull_request -W .github/workflows/main.yml -j tests`. Provide secrets via `-s` flags or `.secrets` when needed.

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
  --set bot.youtubeApiKey="your-api-key" \
  --set bot.webhook.callbackUrl="https://your-domain.com/webhook/youtube"

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

### Database Backup & Restore

- **Helm values**: Configure OCI Object Storage via `objectStorage.*` keys (endpoint, namespace, region, bucket, prefix, access/secret keys, lifecycleDays). Daily CronJob settings live under `backupJob.*`. Example override:
  ```yaml
  objectStorage:
    endpoint: "https://<namespace>.compat.objectstorage.<region>.oraclecloud.com"
    namespace: "<namespace>"
    region: "<region>"
    bucket: "youtube-updater-backups"
    prefix: "db-backups/"
    accessKey: "${OCI_ACCESS_KEY}"
    secretKey: "${OCI_SECRET_KEY}"
    lifecycleDays: 30
  backupJob:
    schedule: "0 2 * * *"
  ```
- **Credential prerequisite**: Keep `objectStorage.enabled` set to `false` until the access and secret keys are populated in the chart Secret (or external secrets provider). Enabling backups without credentials causes the restore init container and backup CronJob to no-op, leaving deployments without protection.
- **CronJob**: `kubectl logs cronjob/<release>-backup` verifies uploads at 02:00 UTC. The job mounts the same PVC as the StatefulSet.
- **Integration pipeline**: Install dev dependencies (`uv sync --group dev`) and ensure `pytest-docker` is available, then run `UV_CACHE_DIR=.uv-cache uv run pytest tests/integration/test_backup_restore_minio.py -m integration -k minio`. The test suite auto-starts a MinIO container via `pytest-docker` and validates backup, restore, and lifecycle retention commands end-to-end (tests skip automatically if the plugin or Docker is unavailable).

## Database Migration (Chat Support rollout)

Story 1.9 introduces chat-aware subscriptions and replaces `subscriptions.user_id`/`notifications.user_id` with `chat_id`. Rollout steps:

1. **Backup first** – capture a SQLite dump (`.backup` in the CLI) or database snapshot.
2. **Install Alembic** – now bundled with the project (`pip install -e .` already pulls `alembic>=1.13.2`).
3. **Run migrations** – execute:
   ```bash
   alembic -x db_url="$DATABASE_URL" upgrade head
   ```
   The script creates the `chats` table, migrates existing personal subscriptions into chat records (`type='private'`), and swaps repository foreign keys over to chats.
4. **Verify data** – confirm `subscriptions.chat_id` and `notifications.chat_id` are populated, and that the bot can list subscriptions for both private and shared chats.
5. **Rollback plan** – if needed, downgrade with `alembic -x db_url="$DATABASE_URL" downgrade -1` immediately after migration; this rehydrates `user_id` columns and drops chat tables (group data will be collapsed into pseudo users).

Fresh environments call `alembic upgrade head` automatically via `init_db()` during bot startup, so no manual action is required for new installs.
- **Startup auto-restore**: Init container runs `python scripts/restore-db.py --destination-path /app/data/bot.db` when the database file is missing.
- **Manual validation (MinIO/OCI compatible)**:
  1. Export credentials/environment variables (`OBJECT_STORAGE_*`) and run `python scripts/backup-db.py --database-path ./data/bot.db`.
  2. Delete `data/bot.db`, then run `python scripts/restore-db.py --destination-path ./data/bot.db`.
  3. Start the bot; it restores automatically if the DB is absent and logs success (`Database restore completed`).
- **Retention policy**: Apply 30-day lifecycle with OCI CLI (replace placeholders):
  ```bash
  oci os object-lifecycle-policy put \
    --bucket-name youtube-updater-backups \
    --namespace <namespace> \
    --items '[
      {"action":"DELETE","timeAmount":30,"timeUnit":"DAYS","isEnabled":true,
       "objectNameFilter":{"prefix":"db-backups/"}}
    ]'
  ```
- **Troubleshooting**: `python scripts/backup-db.py --object-prefix test/ --database-path /tmp/bot.db` uploads test artifacts; `python scripts/restore-db.py --force` overwrites existing files for recovery drills.

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
uv pip install -e ".[dev]"

# Production installation (core dependencies only)
uv pip install -e .

# From PyPI (when published)
uv pip install youtube-updater-tg-bot
```

### Dependencies
- **Core**: python-telegram-bot, starlette, uvicorn, SQLAlchemy, httpx, pydantic
- **Dev**: pytest, ruff, mypy, pre-commit, allure-pytest

### Configuration Files
- `pyproject.toml` - Main project configuration and dependencies
- `requirements.txt` - Legacy dependency file (maintained for compatibility)
- `.env.example` - Environment variables template

### Environment Configuration

**Required Environment Variables:**
- `TELEGRAM_BOT_TOKEN` - Telegram bot token from BotFather
- `YOUTUBE_API_KEY` - YouTube Data API v3 key
- `WEBHOOK_CALLBACK_URL` - Full publicly accessible URL for YouTube webhook notifications
  - **Development**: `http://localhost:8000/webhook/youtube`
  - **Production**: Must use HTTPS (e.g., `https://<hostname>/webhook/youtube`)
  - **Validation**: Production URLs must use HTTPS; only localhost allowed for HTTP

**Optional Environment Variables:**
- `DATABASE_URL` - Database connection string (default: `sqlite+aiosqlite:///./bot.db`)
- `WEBHOOK_HOST` - Webhook server host (default: `localhost`)
- `WEBHOOK_PORT` - Webhook server port (default: `8000`)
- `WEBHOOK_PATH` - Webhook endpoint path (default: `/webhook`)
- `LOG_LEVEL` - Logging level (default: `INFO`)

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
