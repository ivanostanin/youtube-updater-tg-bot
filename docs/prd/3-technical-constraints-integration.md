# 3. Technical Constraints & Integration

## 3.1 Existing Technology Stack

| Category | Technology | Version | Purpose |
|----------|-----------|---------|---------|
| **Language** | Python | 3.13 | Core runtime (backwards compatible to 3.11) |
| **Bot Framework** | python-telegram-bot | 22.5 | Telegram Bot API client with async support |
| **Web Framework** | Starlette | 0.48.0 | ASGI framework for webhook server |
| **ASGI Server** | Uvicorn | 0.37.0 | Production-grade async HTTP server |
| **ORM** | SQLAlchemy | 2.0.43 | Async database abstraction layer |
| **Database (Dev)** | SQLite + aiosqlite | 0.21.0 | File-based database with async driver |
| **Database (Prod)** | PostgreSQL (planned) | TBD | Production-grade RDBMS |
| **HTTP Client** | httpx | 0.28.1 | Async HTTP client for API calls |
| **Validation** | Pydantic | 2.11.10 | Data validation and settings management |
| **Feed Parser** | feedparser | 6.0.12 | Parse Atom XML from PubSubHubbub |
| **Testing** | pytest + pytest-asyncio | 8.4.2 / 1.2.0 | Async-compatible test framework |
| **Test Reporting** | allure-pytest | 2.15.0 | Rich test visualization and reporting |
| **Linting** | ruff | 0.14.0 | Fast Python linter and formatter |
| **Type Checking** | mypy | 1.18.2 | Static type analysis (strict mode) |
| **Pre-commit** | pre-commit | 4.3.0 | Git hooks for code quality |
| **Containerization** | Docker | Latest | Container packaging |
| **Orchestration** | Kubernetes + Helm | 1.24+ | Production deployment |
| **Build System** | Hatchling | Latest | Modern Python build backend |

**External Dependencies:**
- **YouTube Data API v3** - Channel/video metadata resolution, quota: 10,000 units/day free tier
- **PubSubHubbub Hub** - https://pubsubhubbub.appspot.com/subscribe (Google-hosted)
- **Telegram Bot API** - Message sending and command handling, rate limit: 30 messages/second

**Version Constraints:**
- Python 3.13 required for development (3.11+ supported for deployment)
- SQLAlchemy 2.0+ required for modern async support
- Type hints use Python 3.13 syntax (may need adjustments for older Python versions)

## 3.2 Integration Approach

### Database Integration Strategy

**Current Implementation (src/database/):**

```
├── models.py           # SQLAlchemy declarative models
├── database.py         # AsyncEngine and session factory
└── repository.py       # Repository pattern for data access
```

**Integration Pattern:**
- Async session management via `AsyncSessionLocal()` context manager
- Repository pattern abstracts CRUD operations from business logic
- Models use SQLAlchemy 2.0 style (declarative base, clear async boundaries)
- Database URL configurable via environment variable (enables SQLite→PostgreSQL migration)

**Migration Path to PostgreSQL:**
1. Install asyncpg driver: `pip install asyncpg`
2. Update `DATABASE_URL`: `postgresql+asyncpg://user:pass@host/db`
3. Run Alembic migrations for schema initialization
4. No application code changes required (SQLAlchemy abstraction)

**Data Models:**

```python
# Current Models
- User: Telegram user information (telegram_id, username, first_name, last_name)
- YouTubeChannel: YouTube channel metadata (channel_id, channel_name, feed_url)
- Subscription: User-Channel relationship (user_id, channel_id, notification_enabled)
- Video: Video metadata from feeds (video_id, title, published_at, thumbnail_url)
- Notification: Notification delivery log (user_id, video_id, sent_at, message_id)

# Planned Models (Story 1.9)
- Chat: Multi-context support (chat_id, chat_type, title) - replaces User in subscriptions
- Subscription refactored: Uses chat_id instead of user_id for group/channel support
```

### API Integration Strategy

**YouTube Data API (src/youtube/api.py):**
- Async httpx client with connection pooling
- URL resolution methods: `channels.list`, `videos.list`, `playlists.list`
- Quota-aware: Caches feed URLs, minimizes API calls
- Error handling: Graceful fallback on API errors, logs failures with context

**PubSubHubbub Integration (src/webhooks/pubsub.py):**
- **Subscribe:** POST to hub with callback URL and topic (channel feed)
- **Unsubscribe:** POST with `mode=unsubscribe`
- **Verification:** Handle GET requests with `hub.challenge` parameter (echo back)
- **Notifications:** Parse Atom XML feeds from POST requests using feedparser

**Telegram Bot API (src/bot/):**
- ApplicationBuilder with async context management
- Long polling for receiving updates (default mode)
- Async message sending via `bot.send_message()`
- Inline keyboards for interactive commands (InlineKeyboardMarkup)

### Testing Integration Strategy

**Test Framework Architecture:**

```
Testing Stack:
├── pytest 8.4.2                    # Core test framework
├── pytest-asyncio 1.2.0            # Async test support
├── allure-pytest 2.15.0            # Test reporting and visualization
├── unittest.mock                   # Mocking framework (stdlib)
└── pytest-cov (to be added)        # Coverage reporting

Test Directory Structure:
tests/
├── unit/                           # Fast, isolated tests (~100ms per test)
│   ├── test_models.py             # Database model validation
│   ├── test_repository.py         # Repository pattern (mocked DB)
│   ├── test_youtube_api.py        # API client (mocked HTTP responses)
│   ├── test_handlers.py           # Bot handlers (mocked Telegram)
│   └── test_pubsub.py             # PubSubHubbub manager tests
├── integration/                    # Real dependencies (~1-5s per test)
│   ├── test_bot_flow.py           # End-to-end command flows
│   ├── test_webhook_server.py     # Starlette app integration
│   ├── test_database_ops.py       # Real SQLite operations
│   └── test_youtube_integration.py # Real YouTube API calls (marked @slow)
├── fixtures/                       # Shared test fixtures
│   ├── conftest.py                # Pytest fixtures (DB, bot, API clients)
│   └── mock_data.py               # Sample YouTube responses
└── allure_results/                # Generated Allure JSON reports (gitignored)
```

**Allure Test Reporting Framework:**

**Configuration:**
```bash
# Run tests and generate Allure results
pytest --alluredir=allure-results

# Run specific test categories
pytest -m unit --alluredir=allure-results                    # Unit tests only
pytest -m integration --alluredir=allure-results              # Integration tests only
pytest -m "not slow" --alluredir=allure-results              # Skip slow tests

# Generate and serve Allure HTML report
allure serve allure-results                                   # Auto-opens browser
allure generate allure-results -o allure-report --clean      # Generate static HTML
```

**Allure Features:**
- **Feature Organization:** `@allure.feature()` groups tests by functional area
- **User Stories:** `@allure.story()` links tests to user stories from Project Brief
- **Severity Levels:** `@allure.severity()` prioritizes test failures (BLOCKER, CRITICAL, NORMAL, MINOR, TRIVIAL)
- **Test Steps:** `with allure.step()` provides detailed execution flow for debugging
- **Attachments:** `allure.attach()` captures API responses, logs, database state for failures
- **Links:** `@allure.issue()`, `@allure.testcase()` connect to GitHub issues and test management

**Test Strategy:**

```
Test Pyramid:
                 /\
                /  \
               / E2E \          ~5% (Slow integration tests)
              /--------\
             /          \
            / Integration \     ~20% (API/DB integration)
           /--------------\
          /                \
         /   Unit Tests     \   ~75% (Fast, isolated)
        /____________________\
```

**Coverage Target: 70%+ (currently ~0% - tests to be implemented)**

**Allure Test Organization by Feature:**

| Feature | Stories | Unit Tests | Integration Tests | Total |
|---------|---------|------------|-------------------|-------|
| Subscription Management | Subscribe, Unsubscribe, List | 15 | 5 | 20 |
| YouTube API Integration | URL Resolution, Metadata | 10 | 3 | 13 |
| Webhook Processing | PubSub Subscribe, Notifications | 12 | 4 | 16 |
| Notification Delivery | Message Formatting, Sending | 8 | 3 | 11 |
| Database Operations | CRUD, Queries | 18 | 6 | 24 |
| **Total** | **12 stories** | **63** | **21** | **84** |

### Code Organization and Standards

**File Structure:**

```
youtube-updater-tg-bot/
├── src/                           # Main application package
│   ├── bot/                       # Telegram bot logic
│   │   ├── bot.py                 # Bot initialization and runner
│   │   ├── handlers.py            # Command and message handlers
│   │   └── notifications.py       # Notification formatting and sending
│   ├── youtube/                   # YouTube API integration
│   │   └── api.py                 # URL resolution and metadata fetching
│   ├── webhooks/                  # PubSubHubbub webhook handling
│   │   ├── handlers.py            # Starlette app and routes
│   │   └── pubsub.py              # Hub subscription management
│   ├── database/                  # Data layer
│   │   ├── models.py              # SQLAlchemy models
│   │   ├── database.py            # Engine and session configuration
│   │   └── repository.py          # Data access repositories
│   ├── premium/                   # Future AI features (placeholder)
│   ├── utils/                     # Shared utilities
│   │   ├── config.py              # Pydantic settings
│   │   └── logging.py             # Logging configuration
│   └── main.py                    # Application entry point
├── tests/                         # Test suite
├── scripts/                       # Utility scripts
│   ├── docker-build.sh
│   ├── docker-push.sh
│   ├── docker-run.sh
│   ├── backup-db.py              # (To be added - Story 1.2)
│   └── restore-db.py             # (To be added - Story 1.2)
├── deployment/                    # Deployment configuration
│   ├── docker/
│   │   └── Dockerfile
│   └── helm/
│       └── youtube-updater-tg-bot/  # Helm chart
├── docs/                          # Project documentation
│   ├── brief.md                   # Project brief
│   └── tech-spec.md               # This document
├── pyproject.toml                 # Project configuration
├── README.md                      # User documentation
├── CLAUDE.md                      # Developer documentation
└── .env.example                   # Environment variable template
```

**Naming Conventions:**
- Packages: `lowercase_with_underscores`
- Modules: `lowercase_with_underscores.py`
- Classes: `PascalCase` (YouTubeAPI, BotHandlers, UserRepository)
- Functions/methods: `lowercase_with_underscores`
- Constants: `UPPERCASE_WITH_UNDERSCORES`
- Private members: `_leading_underscore`

**Coding Standards (Enforced via pyproject.toml):**

**Ruff (Linter/Formatter):**
- Line length: 100 characters
- Target: Python 3.13
- Enabled rules: pycodestyle (E/W), pyflakes (F), isort (I), pep8-naming (N), pyupgrade (UP), bugbear (B), comprehensions (C4), simplify (SIM), tidy-imports (TID)
- Import sorting: First-party (`src`) imports grouped separately
- Quote style: double quotes

**Mypy (Type Checker - Strict Mode):**
- `disallow_untyped_defs = true` - All functions must have type hints
- `disallow_incomplete_defs = true` - Partial type hints not allowed
- `check_untyped_defs = true` - Check function bodies even if untyped
- `no_implicit_optional = true` - None must be explicit in unions
- `warn_return_any = true` - Warn on returning Any
- `strict_equality = true` - Strict equality checks
- Ignored imports: `feedparser`, `telegram.*` (no type stubs available)

**Documentation Standards:**

Current state: **Minimal docstrings** (to be improved)

Target standard (Google-style docstrings):
```python
def resolve_url(self, url: str) -> dict[str, Any] | None:
    """
    Resolve a YouTube URL to channel information.

    Args:
        url: YouTube URL (channel, video, or playlist)

    Returns:
        Dictionary with channel info (id, title, url) or None if invalid

    Raises:
        HTTPError: If YouTube API request fails

    Example:
        >>> api = YouTubeAPI(api_key="...")
        >>> result = await api.resolve_url("https://youtube.com/@channel")
        >>> result["id"]
        'UCxxxxxxxxxxxxx'
    """
```

## 3.3 Deployment and Operations

### Build Process Integration

**Local Development:**
```bash
1. Source virtual environment: source .venv/bin/activate
2. Install dependencies: uv pip install -e ".[dev]"
3. Run pre-commit hooks: pre-commit install && pre-commit run --all-files
4. Run tests: pytest --alluredir=allure-results
5. Type check: mypy src/ tests/
6. Lint: ruff check src/ tests/
7. Format: ruff format src/ tests/
8. Run bot: python -m src.main
```

**Docker Build:**
```bash
./scripts/docker-build.sh [-t TAG] [-p PLATFORM] [--push]
- Builds multi-stage Dockerfile
- Supports linux/amd64 and linux/arm64
- Pushes to Docker Hub if --push flag provided
```

**Package Build (PyPI distribution):**
```bash
python -m build
- Creates wheel and sdist in dist/
- Ready for pip install or PyPI upload
```

### Deployment Strategy

**Target Environment:** Kubernetes (OCI cluster)

**Deployment Flow:**
1. Code push to GitHub (main branch)
2. GitHub Actions triggered:
   - Run tests (pytest with Allure)
   - Type check (mypy)
   - Lint (ruff check)
   - Build Docker image
   - Push to Docker Hub with git SHA tag
3. Helm upgrade (manual or automated):
   ```bash
   helm upgrade youtube-updater-tg-bot deployment/helm/youtube-updater-tg-bot \
     --set image.tag=<git-sha> \
     --set bot.telegramBotToken=<secret> \
     --set bot.youtubeApiKey=<secret>
   ```

**Deployment Components:**
- **Deployment:** Single pod (stateless, can scale horizontally)
- **Service:** ClusterIP exposing webhook port (8000)
- **Ingress:** HTTPS endpoint for webhook callbacks (youtube-bot.nmro.cc)
- **PersistentVolumeClaim:** SQLite database storage (10Gi)
- **Secrets:** Telegram token, YouTube API key (Kubernetes secrets or External Secrets Operator)
- **ConfigMap:** Non-sensitive configuration (log level, webhook path)

**Rollout Strategy:**
- RollingUpdate with `maxUnavailable=0`, `maxSurge=1`
- Health checks: readiness (webhook `/health` endpoint), liveness (process check)
- Graceful shutdown: SIGTERM handling in `main.py` `cleanup()`

**Database Backup Strategy:**
- **SQLite:** Scheduled CronJob copies `bot.db` to the configured S3-compatible object storage endpoint (OCI Object Storage by default) daily at 02:00 UTC using Helm-provided credentials and settings.
- **Restore:** InitContainer/startup hook fetches the latest verified backup from the same object storage configuration when `bot.db` is missing, logging outcomes and gracefully handling empty buckets.
- **PostgreSQL migration:** Use managed service (RDS, Cloud SQL) with automated backups

### Monitoring and Logging

**Logging Configuration (src/utils/logging.py):**
- Format: JSON structured logs (timestamp, level, message, context)
- Levels: DEBUG (dev), INFO (prod), WARNING, ERROR, CRITICAL
- Output: stdout (captured by Kubernetes)
- Rotation: Handled by container orchestration

**Log Aggregation:**
- Target: Grafana Loki or ELK stack
- Queries: Filter by logger name, level, user_id, channel_id

**Key Metrics to Track:**
- `telegram_commands_total` (counter, by command)
- `webhook_notifications_received_total` (counter)
- `subscription_count` (gauge)
- `youtube_api_calls_total` (counter, track quota usage)
- `notification_delivery_latency_seconds` (histogram)
- `error_rate` (counter, by error type)

**Alerting:**
- YouTube API quota >80% consumed → WARNING
- Webhook endpoint unreachable → CRITICAL
- Database connection failures → CRITICAL
- Error rate >5% → WARNING

### Configuration Management

**Environment Variables (Pydantic Settings):**

**Required:**
- `TELEGRAM_BOT_TOKEN`: Bot token from @BotFather
- `YOUTUBE_API_KEY`: YouTube Data API v3 key

**Optional (with defaults):**
- `DATABASE_URL`: `sqlite+aiosqlite:///./bot.db`
- `WEBHOOK_HOST`: `localhost` (override with public domain)
- `WEBHOOK_PORT`: `8000`
- `WEBHOOK_PATH`: `/webhook`
- `WEBHOOK_CALLBACK_URL`: (to be added - Story 1.1)
- `LOG_LEVEL`: `INFO`

**Backup & Restore Configuration (Story 1.2):**
- `OBJECT_STORAGE_ENDPOINT`: Custom S3-compatible endpoint URL (set for OCI Object Storage; leave blank for AWS default).
- `OBJECT_STORAGE_NAMESPACE`: OCI namespace used for bucket addressing (optional for AWS).
- `OBJECT_STORAGE_REGION`: Region for the object storage client (e.g., `us-ashburn-1`).
- `OBJECT_STORAGE_BUCKET`: Bucket name (required when backups are enabled; prefix namespace if required by provider).
- `OBJECT_STORAGE_PREFIX`: Object key prefix (default `db-backups/`).
- `OBJECT_STORAGE_USE_NAMESPACE_PATH`: `"true"`/`"false"` flag to toggle namespace-prefixed paths for OCI compatibility.
- `OBJECT_STORAGE_VERIFY_SSL`: `"true"`/`"false"` flag controlling SSL verification against custom endpoints.
- `OBJECT_STORAGE_LIFECYCLE_DAYS`: Integer string representing retention window (default `30`).
- `OBJECT_STORAGE_ACCESS_KEY` / `OBJECT_STORAGE_SECRET_KEY`: Credentials injected via Kubernetes Secret for backup/restore scripts.

**Kubernetes Deployment:**
```bash
# 1. Store secrets in Kubernetes Secrets
kubectl create secret generic youtube-bot-secrets \
  --from-literal=telegram-token=<token> \
  --from-literal=youtube-api-key=<key>

# 2. Reference in Helm values.yaml
env:
  - name: TELEGRAM_BOT_TOKEN
    valueFrom:
      secretKeyRef:
        name: youtube-bot-secrets
        key: telegram-token

# 3. Use External Secrets Operator for production (vault integration)
```

## 3.4 Risk Assessment and Mitigation

### Technical Risks

**Risk 1: YouTube API Quota Exhaustion**
- **Description:** 10,000 units/day limit may be exceeded with many users
- **Impact:** HIGH - Bot cannot resolve new URLs or fetch metadata
- **Probability:** MEDIUM - Depends on growth rate
- **Mitigation:**
  - Implement response caching for channel metadata (TTL: 24h)
  - Use webhook-based notifications (no polling = zero quota for notifications)
  - Monitor quota usage via metrics (`youtube_api_calls_total`)
  - Request quota increase from Google (cost: ~$0.40 per additional 1,000 units)
  - Fallback: Rate limit new subscriptions during high usage periods

**Risk 2: PubSubHubbub Reliability**
- **Description:** Google-hosted hub service could become unreliable or deprecated
- **Impact:** HIGH - No real-time notifications without webhook service
- **Probability:** LOW - Service has been stable for 10+ years
- **Mitigation:**
  - Implement fallback polling mechanism (disabled by default, code ready)
  - Monitor webhook success rate via metrics
  - Alternative: Self-hosted Superfeedr or polling-only mode
  - Document migration path to RSS polling if hub service ends

**Risk 3: SQLite Scalability Limits**
- **Description:** SQLite may struggle with concurrent writes at scale (>1000 users)
- **Impact:** MEDIUM - Slower response times, potential lock timeouts
- **Probability:** MEDIUM - Current threading model + async may encounter issues
- **Mitigation:**
  - Design for PostgreSQL migration from start (SQLAlchemy abstraction maintained)
  - Implement connection pooling configuration
  - Test under load (>10K subscriptions, >100 concurrent users)
  - Migration trigger: Response time p95 >1s OR lock errors >1%
  - See Story 1.10 for migration procedure

**Risk 4: Hardcoded Webhook URL (CRITICAL - IMMEDIATE FIX)**
- **Description:** `handlers.py:19` contains hardcoded production URL (`youtube-bot.nmro.cc`)
- **Impact:** LOW (currently) - Dev/staging environments may interfere with production
- **Probability:** HIGH - Already exists in code
- **Mitigation:** **Story 1.1 (P0)** - Move to environment variable `WEBHOOK_CALLBACK_URL`

### Integration Risks

**Risk 5: Telegram Rate Limiting**
- **Description:** Bot may be rate-limited during high notification volume
- **Impact:** MEDIUM - Delayed or failed notifications
- **Probability:** MEDIUM - Depends on channel upload frequency
- **Mitigation:**
  - Respect rate limits: 30 messages/second globally, 1 message/second per chat
  - Implement message queue with rate limiter (asyncio Semaphore)
  - Batch notifications for multiple videos from same channel
  - Monitor `telegram_api_errors` metric

**Risk 6: Webhook Endpoint Availability**
- **Description:** Public webhook endpoint could be unreachable (DNS, ingress, DDoS)
- **Impact:** HIGH - No notifications delivered
- **Probability:** LOW-MEDIUM - Depends on infrastructure reliability
- **Mitigation:**
  - Use managed ingress controller with DDoS protection (Cloudflare recommended)
  - Implement health check endpoint: `GET /health`
  - Monitor uptime externally (UptimeRobot, Pingdom)
  - Set up alerts for ingress errors
  - Webhook verification: Validate `hub.challenge` on subscription

### Deployment Risks

**Risk 7: Database State Loss**
- **Description:** Pod restart could lose SQLite database if PVC not configured
- **Impact:** CRITICAL - All subscriptions lost
- **Probability:** LOW - Helm chart includes PVC, but misconfiguration possible
- **Mitigation:**
  - Mandatory PVC in Helm chart (cannot be disabled)
  - Automated OCI object storage (S3-compatible) backups (**Story 1.2 - P0**)
  - Restore on startup: Check the configured object storage for the latest backup if `bot.db` missing
  - Test restore procedure regularly (monthly)
  - PostgreSQL migration eliminates this risk (Story 1.10)

**Risk 8: Secrets Exposure**
- **Description:** API keys could be exposed in logs, environment dumps, or code
- **Impact:** CRITICAL - Unauthorized access, API abuse, bot hijacking
- **Probability:** LOW - Current implementation uses environment variables correctly
- **Mitigation:**
  - Never log full tokens (truncate to first 8 chars in logs)
  - Use Kubernetes Secrets with RBAC
  - Rotate tokens regularly (quarterly)
  - Implement External Secrets Operator for vault integration
  - Audit: grep for "token" and "api_key" in code reviews
  - Pre-commit hook to detect accidentally committed secrets

### Mitigation Strategies Summary

| Priority | Risk | Action | Timeline |
|----------|------|--------|----------|
| **P0** | Hardcoded webhook URL | Move to configuration (Story 1.1) | Sprint 1 |
| **P0** | Database backups | Implement S3-compatible backup CronJob with OCI Object Storage (Story 1.2) | Sprint 1 |
| **P1** | YouTube quota monitoring | Add quota usage metrics (Story 1.5) | Sprint 3 |
| **P1** | Telegram rate limiting | Implement message queue | Sprint 3-4 |
| **P0** | SQLite→PostgreSQL | Plan migration, test under load (Story 1.10) | Sprint 2 (accelerated from backlog) |
| **P2** | PubSubHubbub fallback | Design polling fallback (don't implement yet) | Backlog |
| **P3** | Secrets rotation | Document rotation procedure | Sprint 2 |

---
