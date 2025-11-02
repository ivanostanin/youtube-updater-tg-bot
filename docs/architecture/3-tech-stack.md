# 3. Tech Stack

## 3.1 Existing Technology Stack

| Category            | Current Technology             | Version | Usage in Enhancement                               | Notes                                                                      |
|---------------------|--------------------------------|---------|----------------------------------------------------|----------------------------------------------------------------------------|
| Language            | Python                         | 3.13    | Core language for all enhancements                 | Maintained throughout                                                      |
| Bot Framework       | python-telegram-bot            | 22.5    | Bot handlers, command processing, ACL verification | Core dependency; will use getChatMember API for admin verification         |
| Bot Extensions      | python-telegram-bot[job-queue] | 22.5    | Background jobs for auto-deletion scheduler        | Used for scheduled message cleanup                                         |
| Web Framework       | Starlette                      | 0.48.0  | Webhook HTTP server                                | Maintained for YouTube webhook handling; no changes required               |
| ASGI Server         | Uvicorn (with standard extras) | 0.37.0  | Production async web server                        | Maintained in webhook server thread                                        |
| ORM                 | SQLAlchemy (with asyncio)      | 2.0.43  | Async database operations, new models              | Will add Alembic for migrations                                            |
| SQLite Driver       | aiosqlite                      | 0.21.0  | Async SQLite connection                            | Development and initial production; Phase 3 may add asyncpg for PostgreSQL |
| HTTP Client         | httpx                          | 0.28.1  | YouTube API, PubSubHubbub, LLM APIs                | Will extend for OpenAI/Anthropic premium features                          |
| Data Validation     | Pydantic                       | 2.11.10 | Settings, request/response models                  | Used for LLM request/response schemas                                      |
| Settings Management | pydantic-settings              | 2.11.0  | Environment configuration                          | Will add new settings for LLM API keys, deletion intervals                 |
| Multipart Forms     | python-multipart               | 0.0.20  | Webhook request parsing                            | Maintained for compatibility                                               |
| Feed Parsing        | feedparser                     | 6.0.12  | Atom XML webhook parsing                           | Maintained for YouTube notifications                                       |
| Testing Framework   | pytest                         | 8.4.2   | Unit and integration tests                         | Will expand for comprehensive test coverage (Phase 1)                      |
| Async Testing       | pytest-asyncio                 | 1.2.0   | Async test support                                 | Required for testing async handlers and repositories                       |
| Test Reporting      | allure-pytest                  | 2.15.0  | Test result visualization                          | Optional for CI/CD integration                                             |
| Linter/Formatter    | ruff                           | 0.14.0  | Code quality enforcement                           | Maintained with 100-char line length                                       |
| Type Checker        | mypy                           | 1.18.2  | Static type validation                             | Maintained with strict mode for new code                                   |
| Pre-commit Hooks    | pre-commit                     | 4.3.0   | Git hook management                                | Enforces ruff and mypy before commits                                      |

## 3.2 New Technology Additions

| Technology        | Version | Purpose                                          | Rationale                                                                                                                          | Integration Method                                                                                       |
|-------------------|---------|--------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| Alembic           | 1.13.2+ | Database migration framework                     | Required for safe schema evolution (NFR23); industry-standard SQLAlchemy migration tool                                            | Install as dev dependency; initialize with `alembic init migrations/`; integrate with existing database.py |
| OpenAI Python SDK | 1.12.0+ | LLM API client for video summaries (Phase 3)     | Official OpenAI library for GPT-4/GPT-4-Turbo integration; handles auth, retries, streaming                                        | Optional dependency in [premium] extras; configure via OPENAI_API_KEY env var                            |
| Anthropic SDK     | 0.18.0+ | Alternative LLM provider for summaries (Phase 3) | Claude API for cost optimization and long-context summarization; fallback option                                                   | Optional dependency in [premium] extras; configure via ANTHROPIC_API_KEY env var                         |
| APScheduler       | 3.10.4+ | Advanced background job scheduling               | More robust than python-telegram-bot's job_queue for complex schedules (auto-deletion, webhook renewal); supports cron expressions and persistence | Install as core dependency; replace job_queue usage for deletion scheduler                               |
| redis (aioredis)  | 5.0.1+  | Distributed caching for LLM responses (Phase 3)  | Cache transcript summaries to reduce API costs; support multi-instance deployments                                                 | Optional dependency in [premium] extras; connect via REDIS_URL env var                                   |
| asyncpg           | 0.29.0+ | PostgreSQL async driver (Phase 3)                | Required for SQLite → PostgreSQL migration; high-performance async operations                                                      | Optional dependency in [postgres] extras; SQLAlchemy will use automatically when configured              |


## 3.3   Rationale & Key Decisions:

  Why Maintain Existing Stack:
  1. Stability: Current versions (python-telegram-bot 22.5, SQLAlchemy 2.0, Pydantic 2.11) are mature LTS releases with no breaking changes expected
  2. Async Consistency: Entire stack is async-compatible (aiosqlite, httpx, asyncio); maintains your existing async/await patterns
  3. Developer Familiarity: Continuing with established libraries reduces learning curve and maintains code consistency

  New Technology Justifications:

  - Alembic (Required): Your codebase currently uses Base.metadata.create_all() which provides no migration history or rollback capability. Alembic is the industry-standard solution for SQLAlchemy
  migrations and is required for NFR23. Alternative Considered: Manual SQL migration scripts, but rejected due to lack of version control and rollback safety.
  - OpenAI/Anthropic SDKs (Phase 3): While you could use raw httpx calls to LLM APIs, official SDKs provide retry logic, error handling, and streaming support out-of-the-box. Both are optional
  dependencies (pip install -e ".[premium]") to keep core bot lightweight. Trade-off: Adds ~10MB to Docker image when installed.
  - APScheduler (Recommended): python-telegram-bot's job_queue is basic (interval/one-time only). APScheduler provides cron expressions, job persistence (survives restarts), and better observability
  for production auto-deletion scheduling. Alternative: Stick with job_queue for simpler deployments if persistence isn't critical.
  - Redis (Phase 3): LLM API calls are expensive (~$0.03-0.10 per summary). Caching responses in Redis enables multi-instance deployments to share cache and reduces costs. Alternative: In-memory
  cache (functools.lru_cache) works for single-instance, but doesn't scale.
  - asyncpg (Phase 3): Required only if migrating to PostgreSQL for production scale. SQLite with aiosqlite is sufficient for <10k subscriptions. Decision Point: Defer until scalability requirements
  confirmed.

  Version Selection:
  - All new dependencies use current stable releases (as of 2025-01)
  - Minimum versions specified with >= to allow patch updates
  - Optional dependencies grouped in pyproject.toml extras: [dev], [premium], [postgres]

  Areas Needing Validation:
  - APScheduler vs job_queue: Do you need job persistence (survive pod restarts), or is ephemeral scheduling acceptable?
  - LLM Provider Preference: OpenAI (faster, more expensive) vs Anthropic (longer context, cheaper)? Or support both with fallback?
  - Redis Requirement: Single-instance deployment acceptable, or planning multi-replica Kubernetes deployment from start?

---
