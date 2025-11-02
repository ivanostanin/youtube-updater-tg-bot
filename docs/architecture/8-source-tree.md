# 8. Source Tree

## 8.1 Existing Project Structure

```
youtube-updater-tg-bot/
├── src/
│   ├── __init__.py
│   ├── main.py                    # Application entry point
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── bot.py                 # YouTubeUpdaterBot class
│   │   ├── handlers.py            # Command handlers (start, subscribe, list, etc.)
│   │   └── notifications.py       # NotificationService
│   ├── database/
│   │   ├── __init__.py
│   │   ├── database.py            # Database initialization
│   │   ├── models.py              # SQLAlchemy models (User, Channel, etc.)
│   │   └── repository.py          # Repository pattern implementations
│   ├── webhooks/
│   │   ├── __init__.py
│   │   ├── handlers.py            # Starlette webhook routes
│   │   └── pubsub.py              # PubSubManager for hub subscriptions
│   ├── youtube/
│   │   ├── __init__.py
│   │   └── api.py                 # YouTubeAPI client
│   └── utils/
│       ├── __init__.py
│       ├── config.py              # Pydantic settings
│       └── logging.py             # Logging configuration
├── tests/                          # (Empty - to be created)
├── deployment/
│   ├── docker/
│   │   └── Dockerfile
│   └── helm/
│       └── youtube-updater-tg-bot/
├── scripts/                        # Build/deploy scripts
├── .github/workflows/              # CI/CD pipelines
└── pyproject.toml                  # Project configuration
```

## 8.2 New File Organization

```
youtube-updater-tg-bot/
├── src/
│   ├── bot/
│   │   ├── handlers.py            # Existing (add new command methods)
│   │   ├── notifications.py       # Existing (enhance with preferences)
│   │   └── middleware.py          # NEW - ACL enforcement middleware
│   ├── database/
│   │   ├── models.py              # Existing (add Chat, Preference, etc. models)
│   │   ├── repository.py          # Existing (add new repositories)
│   │   └── migrations/            # NEW - Alembic migrations
│   │       ├── env.py
│   │       ├── script.py.mako
│   │       └── versions/
│   │           ├── 001_add_chat_model.py
│   │           ├── 002_add_preferences.py
│   │           └── 003_add_deletion_queue.py
│   ├── services/                  # NEW - Business logic layer
│   │   ├── __init__.py
│   │   ├── acl.py                 # ACLService
│   │   ├── preferences.py         # PreferenceManager
│   │   ├── history.py             # HistoryService
│   │   └── deletion.py            # DeletionScheduler
│   ├── premium/                   # NEW - Premium features (Phase 3)
│   │   ├── __init__.py
│   │   ├── llm_client.py          # LLMClient abstraction
│   │   ├── transcript.py          # TranscriptService
│   │   └── tts.py                 # TTSService
│   └── utils/
│       ├── pagination.py          # NEW - History pagination helpers
│       └── formatters.py          # NEW - Message formatting utilities
├── tests/                         # NEW - Test suite
│   ├── __init__.py
│   ├── conftest.py                # Pytest fixtures
│   ├── unit/
│   │   ├── test_acl_service.py
│   │   ├── test_repositories.py
│   │   └── test_handlers.py
│   ├── integration/
│   │   ├── test_subscription_flow.py
│   │   └── test_webhook_processing.py
│   └── fixtures/
│       └── sample_data.py
├── alembic.ini                    # NEW - Alembic configuration
└── .env.example                   # Update with new env vars
```

## 8.3 Integration Guidelines

### 8.3.1 File Naming

- Follow existing snake_case convention (e.g., `deletion_scheduler.py`, not `deletionScheduler.py`)
- Service classes named with Service or Manager suffix (ACLService, PreferenceManager)
- Repository classes maintain Repository suffix

### 8.3.2 Folder Organization

- New `services/` directory at same level as `bot/`, `database/` for business logic layer
- `premium/` directory separate from core to enable optional installation (`pip install -e ".[premium]"`)
- `tests/` mirrors `src/` structure (`tests/unit/services/test_acl.py` tests `src/services/acl.py`)

### 8.3.3 Import/Export Patterns

- Each package (`services/`, `premium/`) has `__init__.py` exporting public classes
- Absolute imports preferred: `from src.services.acl import ACLService`
- Avoid circular imports: services depend on repositories, not vice versa

---
