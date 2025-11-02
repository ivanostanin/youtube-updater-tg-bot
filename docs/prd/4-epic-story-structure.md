# 4. Epic & Story Structure

## 4.1 Epic Approach

**Single Epic: Production Readiness & Phase 2 Features**

Based on analysis of the existing project, this enhancement is structured as **a single comprehensive epic** rather than multiple epics.

**Rationale:**
1. **Current State:** MVP is functionally complete but needs production hardening
2. **Cohesive Goal:** All remaining work supports the same objective - production deployment + Phase 2 features
3. **Shared Dependencies:** Stories share common infrastructure (database, deployment, testing)
4. **Manageable Scope:** ~86 story points total, deliverable in 4-5 sprints (8-10 weeks)
5. **Brownfield Nature:** This is enhancement work on a single codebase, not multiple unrelated features

**Epic Structure Decision:** Single epic titled **"Production Readiness & Phase 2 Enhancements"** with three logical phases:
- **Phase 1: Production Hardening** (Sprint 1) - Critical fixes, testing foundation
- **Phase 2: Core Features & Deployment** (Sprint 2-3) - Group support, monitoring, production deploy
- **Phase 3: Phase 2 Features** (Sprint 3-4) - Auto-deletion, update history
- **Phase 4: Optional Scaling** (Sprint 5) - PostgreSQL migration if needed

This structure ensures:
- Existing functionality remains intact throughout development
- Each story includes verification that current features still work
- Stories are sequenced to minimize risk to the existing system
- Clear rollback points at each story boundary

---

## 4.2 Epic 1: Production Readiness & Phase 2 Enhancements

**Epic Goal:**
Harden the YouTube Updater Telegram Bot for production deployment on Kubernetes with comprehensive testing, monitoring, and Phase 2 features (group/channel support, auto-deletion, update history).

**Success Criteria:**
- Bot deployed to production Kubernetes cluster with 99.9% uptime
- 70%+ test coverage with Allure reporting in CI/CD
- All critical bugs fixed (hardcoded webhook URL, database backups configured)
- Phase 2 features delivered: group/channel support, auto-deletion timers, update history
- Database migration path to PostgreSQL validated
- Zero disruption to existing user subscriptions

**Integration Requirements:**
- All changes must maintain backward compatibility with existing database schema (until Story 1.9 migration)
- Telegram bot commands must remain functional throughout development
- Webhook registration/unregistration must continue working
- No breaking changes to existing user experience

---

## 4.3 Story Details

### Story 1.1: Fix Hardcoded Configuration Issues

**Priority:** P0 (Critical)
**Effort:** 2 story points
**Sprint:** 1
**Reference:** src/bot/handlers.py:19

As a **developer**,
I want **configuration values (webhook URL) moved from code to environment variables**,
so that **dev/staging/prod environments don't interfere with each other**.

**Acceptance Criteria:**

1. **AC1:** Remove hardcoded webhook URL from `src/bot/handlers.py:19`
2. **AC2:** Add `WEBHOOK_CALLBACK_URL` to `src/utils/config.py` Settings class with validation
3. **AC3:** Update `.env.example` with new variable and documentation
4. **AC4:** Update CLAUDE.md and README.md with configuration documentation
5. **AC5:** Verify webhook registration works with configured URL in dev environment
6. **AC6:** Add validation to ensure URL is HTTPS in production (env-based check)

**Integration Verification:**

- **IV1:** Existing subscriptions continue to receive notifications (test with real YouTube channel)
- **IV2:** New subscriptions can be created successfully
- **IV3:** Webhook unsubscribe works correctly
- **IV4:** No changes to database schema or data

**Technical Notes:**
- Default value: `http://localhost:8000/webhook/youtube` (for local dev)
- Production value: Set via environment variable to `https://youtube-bot.nmro.cc/webhook/youtube`
- Validation: Pydantic `HttpUrl` type with HTTPS enforcement for production
- Reference: Risk #4 in Technical Specifications

---

### Story 1.2: Implement Database Backup to S3

**Priority:** P0 (Critical)
**Effort:** 5 story points
**Sprint:** 1

As a **system administrator**,
I want **automated SQLite database backups to S3**,
so that **user subscriptions are protected against data loss**.

**Acceptance Criteria:**

1. **AC1:** Create Python script `scripts/backup-db.py` that uploads `bot.db` to S3 with timestamp
2. **AC2:** Implement restore script `scripts/restore-db.py` that downloads latest backup by date
3. **AC3:** Add Kubernetes CronJob manifest to Helm chart (daily backups at 02:00 UTC)
4. **AC4:** Configure AWS credentials via Kubernetes secrets (AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY)
5. **AC5:** Add backup metadata (timestamp, SHA256 checksum, file size) to S3 object metadata
6. **AC6:** Test backup and restore procedures manually in dev environment
7. **AC7:** Document backup/restore process in CLAUDE.md (operator runbook)
8. **AC8:** Add S3 bucket lifecycle policy for 30-day retention

**Integration Verification:**

- **IV1:** Backup script runs without disrupting bot operations (test during active use)
- **IV2:** Restored database contains all subscriptions and channels (data integrity check)
- **IV3:** Bot reconnects to restored database successfully after pod restart
- **IV4:** No data corruption after restore (verify with test queries)

**Technical Notes:**
- Use `boto3` library for S3 operations (add to dependencies: `boto3>=1.34.0`)
- S3 bucket path: `s3://youtube-bot-backups/db-backups/bot-{timestamp}.db`
- Timestamp format: ISO 8601 (e.g., `2025-11-01T02-00-00Z`)
- Backup retention: 30 days (S3 lifecycle policy)
- Alternative: Use S3-compatible storage (MinIO, Backblaze B2) for cost savings
- Reference: Risk #7 in Technical Specifications

---

### Story 1.3: Setup Comprehensive Test Suite with Allure

**Priority:** P0 (Critical)
**Effort:** 13 story points
**Sprint:** 1-2

As a **developer**,
I want **comprehensive unit and integration tests with Allure reporting**,
so that **I can confidently make changes without breaking existing functionality**.

**Acceptance Criteria:**

1. **AC1:** Create test fixtures in `tests/fixtures/conftest.py` (mock DB, API clients, bot instances)
2. **AC2:** Implement 15+ unit tests for bot handlers (`tests/unit/test_handlers.py`)
3. **AC3:** Implement 10+ unit tests for YouTube API (`tests/unit/test_youtube_api.py`)
4. **AC4:** Implement 12+ unit tests for webhook handling (`tests/unit/test_pubsub.py`)
5. **AC5:** Implement 18+ unit tests for database models/repository (`tests/unit/test_repository.py`)
6. **AC6:** Implement 6+ integration tests for database operations (`tests/integration/test_database_ops.py`)
7. **AC7:** Implement 5+ integration tests for bot flow (`tests/integration/test_bot_flow.py`)
8. **AC8:** Configure Allure decorators (`@allure.feature`, `@allure.story`, `@allure.severity`)
9. **AC9:** Achieve 70%+ test coverage (measured with `pytest-cov`)
10. **AC10:** All tests pass with `pytest --alluredir=allure-results`
11. **AC11:** Add `pytest-cov` to dev dependencies

**Integration Verification:**

- **IV1:** Tests can be run locally with `pytest --alluredir=allure-results`
- **IV2:** Allure report generates successfully with `allure serve allure-results`
- **IV3:** Test suite completes in <5 minutes (unit tests <30s, integration tests <4m30s)
- **IV4:** No false negatives (flaky tests) - rerun 3 times to verify stability

**Technical Notes:**
- Use `@pytest.mark.unit` and `@pytest.mark.integration` markers
- Mock external APIs (YouTube, Telegram) in unit tests using `unittest.mock`
- Use real SQLite database for integration tests (in-memory or temp file)
- Allure severity mapping: P0=BLOCKER, P1=CRITICAL, P2=NORMAL, P3=MINOR
- Reference: Testing Integration Strategy in Technical Specifications
- Target: 84 total tests (63 unit, 21 integration) across 12 user stories

---

### Story 1.4: Configure GitHub Actions CI/CD with Allure Reports

**Priority:** P1 (High)
**Effort:** 5 story points
**Sprint:** 1-2

As a **developer**,
I want **automated testing and Allure reports on every commit**,
so that **I can catch regressions early and track test results over time**.

**Acceptance Criteria:**

1. **AC1:** Create `.github/workflows/test.yml` workflow file
2. **AC2:** Workflow runs on push to main and all pull requests
3. **AC3:** Workflow installs dependencies and runs pytest with Allure
4. **AC4:** Workflow generates Allure HTML report
5. **AC5:** Workflow uploads Allure report as GitHub Actions artifact (30-day retention)
6. **AC6:** Configure GitHub Pages deployment for Allure reports at `https://username.github.io/youtube-updater-tg-bot/allure-latest/`
7. **AC7:** Add status badge to README.md showing test pass/fail status
8. **AC8:** Workflow fails PR if tests fail (blocks merge)

**Integration Verification:**

- **IV1:** Workflow triggers successfully on test commit
- **IV2:** All tests pass in CI environment
- **IV3:** Allure report accessible via Actions artifacts tab
- **IV4:** Workflow blocks merge if tests fail

**Technical Notes:**
- Use Ubuntu latest runner with Python 3.13
- Cache pip dependencies for faster builds (reduce build time by ~1min)
- Install Allure CLI for report generation (wget from GitHub releases)
- Parallel test execution if test suite grows >5 min (pytest-xdist)
- Reference: CI/CD Integration in Technical Specifications

---

### Story 1.5: Implement Monitoring and Metrics

**Priority:** P1 (High)
**Effort:** 8 story points
**Sprint:** 3

As a **system operator**,
I want **application metrics and structured logging**,
so that **I can monitor bot health and troubleshoot issues in production**.

**Acceptance Criteria:**

1. **AC1:** Add Prometheus metrics endpoint to webhook server (`/metrics`)
2. **AC2:** Implement key counters: `telegram_commands_total` (by command), `webhook_notifications_received_total`, `youtube_api_calls_total`
3. **AC3:** Implement gauges: `subscription_count`, `active_users_count`
4. **AC4:** Implement histogram: `notification_delivery_latency_seconds`
5. **AC5:** Configure JSON structured logging (timestamp, level, message, user_id, channel_id context fields)
6. **AC6:** Add health check endpoint (`/health`) returning 200 OK with JSON status
7. **AC7:** Update Helm chart with liveness/readiness probe configuration pointing to `/health`
8. **AC8:** Create example Grafana dashboard JSON for key metrics (optional, in docs/)
9. **AC9:** Document metrics and logging format in CLAUDE.md

**Integration Verification:**

- **IV1:** Metrics endpoint returns valid Prometheus format (parseable by Prometheus)
- **IV2:** Counters increment correctly when commands are executed (test with `/start`, `/subscribe`)
- **IV3:** Health endpoint returns 200 while bot is operational, 503 if bot stopped
- **IV4:** Logs are JSON-formatted and contain relevant context (user_id, channel_id when applicable)

**Technical Notes:**
- Use `prometheus_client` library for metrics (add to dependencies)
- Metric labels: `command`, `status`, `error_type`
- JSON logging: Add `python-json-logger` dependency
- Health check response: `{"status": "healthy", "uptime_seconds": 12345}`
- Reference: Monitoring and Logging in Technical Specifications

---

### Story 1.6: Deploy to Production Kubernetes

**Priority:** P0 (Critical)
**Effort:** 8 story points
**Sprint:** 3
**Dependencies:** Stories 1.1, 1.2, 1.5, 1.9 (group support schema must be deployed)

As a **DevOps engineer**,
I want **the bot deployed to production Kubernetes cluster with proper secrets and persistence**,
so that **users can access the service reliably**.

**Acceptance Criteria:**

1. **AC1:** Build and push Docker image to Docker Hub with versioned tag (v0.2.0)
2. **AC2:** Create Kubernetes secrets for `TELEGRAM_BOT_TOKEN`, `YOUTUBE_API_KEY`, `WEBHOOK_CALLBACK_URL`
3. **AC3:** Deploy Helm chart with production values (PVC, ingress, secrets, resource limits)
4. **AC4:** Configure ingress for webhook endpoint (youtube-bot.nmro.cc) with TLS
5. **AC5:** Verify TLS certificate is valid (Let's Encrypt or managed cert)
6. **AC6:** Test end-to-end in production:
   - Private chat: Subscribe to channel → Receive notification
   - Group chat: Admin subscribes → All members see notification
   - Non-admin in group: Subscribe rejected with permission error
7. **AC7:** Configure alerting for pod restarts and critical errors
8. **AC8:** Verify database persistence across pod restarts (simulate restart, check subscriptions)

**Integration Verification:**

- **IV1:** Bot responds to `/start` command in production
- **IV2:** Existing subscriptions (if any) continue working after deployment
- **IV3:** Webhook receives callbacks from YouTube (register test channel, trigger upload)
- **IV4:** Database persists across pod restarts (PVC mounted correctly at `/data`)
- **IV5:** Metrics endpoint accessible at `https://youtube-bot.nmro.cc/metrics` (if exposed)
- **IV6:** Health check passes: `curl https://youtube-bot.nmro.cc/health` returns 200

**Technical Notes:**
- Use rolling update strategy (`maxUnavailable=0`, `maxSurge=1`)
- Resource limits: CPU 500m request/1000m limit, Memory 512Mi request/1Gi limit
- Graceful shutdown timeout: 30 seconds (allow time to close DB connections)
- PVC size: 10Gi (sufficient for ~100K subscriptions)
- Reference: Deployment Strategy in Technical Specifications

---

### Story 1.7: Implement Auto-Deletion Timers (Phase 2 Feature)

**Priority:** P2 (Medium)
**Effort:** 8 story points
**Sprint:** 4
**Dependencies:** Story 1.9 (uses `chats` table instead of `users`)

As a **Telegram user**,
I want **notifications automatically deleted after a configurable time period**,
so that **my chat doesn't get cluttered with old video notifications**.

**Acceptance Criteria:**

1. **AC1:** Add `auto_delete_after_days` column to `chats` table (nullable, default: null = disabled)
2. **AC2:** Create Alembic migration for schema change
3. **AC3:** Implement `/settings` command to configure auto-deletion (options: 1, 3, 7 days, or disable)
4. **AC4:** Store `message_id` when sending notifications (already exists in `notifications` table)
5. **AC5:** Create background task that runs hourly to find and delete old messages
6. **AC6:** Delete messages using Telegram API `deleteMessage()` method
7. **AC7:** Handle errors gracefully (message already deleted, bot removed from chat, insufficient permissions)
8. **AC8:** Update CLAUDE.md and README.md with new feature documentation
9. **AC9:** Add tests for auto-deletion logic (unit tests for selection, integration test for deletion)

**Integration Verification:**

- **IV1:** Existing notifications without auto-delete continue working normally
- **IV2:** Users/chats without auto-delete configured are unaffected
- **IV3:** Subscription/unsubscribe functionality continues working
- **IV4:** Database migration runs successfully (add column without data loss)
- **IV5:** Background task runs without blocking bot operations

**Technical Notes:**
- Use Alembic for database migration: `alembic revision -m "Add auto_delete_after_days to chats"`
- Background task: `asyncio.create_task()` with `asyncio.sleep(3600)` loop in `main.py`
- Telegram rate limit: Respect 30 req/sec limit when deleting in bulk (use Semaphore)
- Query: `SELECT * FROM notifications WHERE sent_at < NOW() - INTERVAL chat.auto_delete_after_days DAY`
- Reference: FR8 in Requirements section

---

### Story 1.8: Implement Update History with Filtering

**Priority:** P2 (Medium)
**Effort:** 8 story points
**Sprint:** 4
**Dependencies:** Story 1.9 (uses `chats` table)

As a **Telegram user**,
I want **to view my notification history with filtering options**,
so that **I can find past videos I missed or want to watch later**.

**Acceptance Criteria:**

1. **AC1:** Implement `/history` command showing last 10 notifications with video title, channel, date, link
2. **AC2:** Add pagination using inline keyboard (Next/Previous buttons with page tracking)
3. **AC3:** Implement `/history <channel_name>` to filter by specific channel (fuzzy match on name)
4. **AC4:** Add date range filtering: `/history 7d` (last 7 days), `/history 30d`, `/history 90d`
5. **AC5:** Display format: "📺 [Channel] - [Video Title]\n⏰ [Date]\n🔗 [Link]"
6. **AC6:** Limit history to last 90 days (performance optimization, configurable)
7. **AC7:** Update help text with new command documentation
8. **AC8:** Add unit tests for filtering logic, integration test for command flow

**Integration Verification:**

- **IV1:** History command doesn't interfere with notification delivery
- **IV2:** Pagination works correctly with >10 results (test with user having 50+ notifications)
- **IV3:** Filtering returns accurate results (test with known data)
- **IV4:** Command responds within 500ms for typical queries (indexed lookups)
- **IV5:** Works in both private chats and groups (group history = shared history for that chat)

**Technical Notes:**
- Query optimization: Use indexed columns (`chat_id`, `sent_at`, `channel_id`)
- Pagination: Store offset in `callback_data` (format: `hist_next_10`, `hist_prev_10`)
- Limit results per page: 10 notifications
- Date filtering: Parse `7d` → `datetime.now() - timedelta(days=7)`
- Reference: FR9 in Requirements section

---

### Story 1.9: Implement Group and Channel Support

**Priority:** P0 (Critical) ⚠️ **UPDATED FROM P2**
**Effort:** 13 story points
**Sprint:** 2 ⚠️ **MOVED UP FROM SPRINT 3-4**
**Dependencies:** Story 1.3 (test foundation), Story 1.4 (CI/CD)

As a **Telegram group administrator**,
I want **to configure YouTube subscriptions for my group**,
so that **all members receive notifications automatically**.

**Strategic Rationale for P0 Priority:**
1. **Market Differentiation:** Group/channel support is key differentiator from competitors
2. **User Expectations:** Telegram group admins are primary user segment (Project Brief)
3. **Adoption Driver:** Groups create network effects - one admin brings 100+ potential users
4. **Technical Foundation:** Database schema changes needed - better to implement before user base grows
5. **Revenue Potential:** Group admins more likely to pay for premium features

**Acceptance Criteria:**

1. **AC1:** Detect chat type (private, group, supergroup, channel) in all handlers
2. **AC2:** Add admin verification for group/channel commands (check user permissions via Telegram API)
3. **AC3:** Refactor database schema to support multiple chat types:
   - Create new `Chat` model: `id`, `chat_id`, `chat_type`, `title`, `created_at`
   - Update `Subscription` model: Change `user_id` → `chat_id` (foreign key to `chats.id`)
   - Migrate existing user subscriptions to new schema (users become chats with `type='private'`)
4. **AC4:** Implement `/subscribe` command working in groups/channels (admin-only)
5. **AC5:** Implement `/list` showing group/channel subscriptions (admin-only)
6. **AC6:** Implement `/unsubscribe` for groups/channels (admin-only)
7. **AC7:** Send notifications to group/channel chat when new videos are uploaded
8. **AC8:** Add group-specific message formatting (discussion prompt for groups)
9. **AC9:** Update all existing handlers to work with both private chats and groups
10. **AC10:** Create Alembic migration for database schema changes with upgrade/downgrade paths
11. **AC11:** Write migration guide documentation in CLAUDE.md for existing users (if any)
12. **AC12:** Add comprehensive tests (unit tests for admin checks, integration tests for group flows)

**Integration Verification:**

- **IV1:** Existing personal subscriptions migrate successfully to new schema (test with prod backup)
- **IV2:** Users can still subscribe in private chats (verify `/subscribe`, `/list`, `/unsubscribe`)
- **IV3:** Bot correctly identifies admin status in test groups (test with non-admin users - should reject)
- **IV4:** Notifications sent to groups are formatted appropriately (no spam, clear attribution)
- **IV5:** Webhook notifications continue working after schema change
- **IV6:** All unit and integration tests pass with new schema (run full test suite)

**Technical Notes:**

**Database Schema Changes:**
```python
# New Chat model (replaces user_id in subscriptions)
class Chat(Base):
    __tablename__ = "chats"
    id = Column(Integer, primary_key=True)
    chat_id = Column(String, unique=True, nullable=False, index=True)
    chat_type = Column(String, nullable=False)  # 'private', 'group', 'supergroup', 'channel'
    title = Column(String, nullable=True)
    username = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    subscriptions = relationship("Subscription", back_populates="chat")

# Updated Subscription model
class Subscription(Base):
    __tablename__ = "subscriptions"
    id = Column(Integer, primary_key=True)
    chat_id = Column(Integer, ForeignKey("chats.id"), nullable=False)  # Changed from user_id
    channel_id = Column(Integer, ForeignKey("youtube_channels.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    chat = relationship("Chat", back_populates="subscriptions")
```

**Admin Verification:**
```python
async def is_user_admin(bot, chat_id: int, user_id: int) -> bool:
    """Check if user is admin in the chat."""
    member = await bot.get_chat_member(chat_id, user_id)
    return member.status in ['creator', 'administrator']
```

**Migration Strategy:**
- Alembic migration file: `alembic/versions/001_add_multi_chat_support.py`
- Create `chats` table
- Migrate existing users to chats (type='private')
- Add `chat_id` column to subscriptions
- Populate `chat_id` from user_id mapping
- Drop old `user_id` column

**Reference:** FR10, Project Brief Secondary User Segment (Telegram Community Managers)

---

### Story 1.10: Database Migration to PostgreSQL (Optional)

**Priority:** P3 (Low)
**Effort:** 8 story points
**Sprint:** 5 (or backlog)
**Trigger:** Response time p95 >1s OR concurrent users >500 OR lock errors >1%

As a **system architect**,
I want **to migrate from SQLite to PostgreSQL**,
so that **the system can scale to thousands of concurrent users**.

**Acceptance Criteria:**

1. **AC1:** Install asyncpg driver and update dependencies in `pyproject.toml`
2. **AC2:** Create PostgreSQL database on managed service (AWS RDS, GCP Cloud SQL, or OCI managed PostgreSQL)
3. **AC3:** Update Helm chart with PostgreSQL connection configuration (host, port, database, credentials)
4. **AC4:** Export SQLite data and import to PostgreSQL (migration script `scripts/migrate-sqlite-to-postgres.py`)
5. **AC5:** Update `DATABASE_URL` environment variable to PostgreSQL connection string
6. **AC6:** Run full test suite against PostgreSQL (all tests pass)
7. **AC7:** Deploy to staging environment and verify functionality (load test with 100+ concurrent subscriptions)
8. **AC8:** Document migration process in CLAUDE.md with rollback procedure
9. **AC9:** Performance test: Verify p95 latency improves and no lock errors

**Integration Verification:**

- **IV1:** All existing subscriptions migrate successfully (data integrity check: count matches)
- **IV2:** Bot functionality identical after migration (subscribe, list, unsubscribe, notifications work)
- **IV3:** Webhook notifications continue delivering to users
- **IV4:** Performance metrics show improvement (query latency p95 <200ms, throughput >100 req/s)
- **IV5:** No database lock errors under load (test with 50 concurrent subscription operations)

**Technical Notes:**
- **Trigger condition:** SQLite response time p95 >1s OR concurrent users >500 OR lock errors >1%
- Connection pooling: Configure SQLAlchemy `pool_size=20`, `max_overflow=40`
- Migration script: Use `sqlite3` + `psycopg2` for data export/import
- Zero downtime migration: Use read replica pattern (PostgreSQL as replica, switch primary)
- Alembic: Run `alembic upgrade head` on new PostgreSQL database to create schema
- Reference: NFR16 in Requirements section, Risk #3 mitigation

---

## 4.4 Story Dependencies and Sprint Schedule

**Sprint Breakdown:**

```
Sprint 1 (Week 1-2): Foundation & Critical Fixes
  Story 1.1 (Fix Config) ────────────────> 2 SP
  Story 1.2 (Database Backups) ──────────> 5 SP
  Story 1.3 (Test Suite) ────────────────> 13 SP
  Total: 20 SP

Sprint 2 (Week 3-4): Core Features & Group Support
  Story 1.4 (CI/CD) ─────────────────────> 5 SP
  Story 1.9 (Groups - P0) ───────────────> 13 SP ⚠️ CRITICAL PATH
  Total: 18 SP

Sprint 3 (Week 5-6): Deployment & Monitoring
  Story 1.5 (Monitoring) ────────────────> 8 SP
  Story 1.6 (Deploy to Prod) ────────────> 8 SP
  Total: 16 SP

Sprint 4 (Week 7-8): Phase 2 Features
  Story 1.7 (Auto-deletion) ─────────────> 8 SP
  Story 1.8 (Update History) ────────────> 8 SP
  Total: 16 SP

Sprint 5 (Week 9-10): Optional Scaling
  Story 1.10 (PostgreSQL) ───────────────> 8 SP (only if triggered by metrics)
```

**Dependency Graph:**

```
Sprint 1:
  1.1 (Config) ──┐
                 ├──> 1.2 (Backups) ──┐
  1.3 (Tests) ───┘                     │
                                       ├──> Sprint 2
                                       │
Sprint 2:                              │
  1.4 (CI/CD) <──────────────────────┘
  1.9 (Groups) <──────────────────┐  ⚠️ P0 Critical
                                  │
  ⚠️ CRITICAL: Story 1.9 schema changes MUST complete
     before Story 1.6 (Production Deploy) in Sprint 3

Sprint 3:
  1.5 (Monitoring) ──┐
                     ├──> 1.6 (Deploy) <── REQUIRES Story 1.9 complete
  1.9 (Complete) ────┘

Sprint 4:
  1.7 (Auto-delete) ──┐
                      ├──> Can work in parallel
  1.8 (History) ──────┘

Sprint 5:
  1.10 (PostgreSQL) ──> Only if scaling metrics trigger threshold
```

**Critical Path:**
`Story 1.1 → 1.2 → 1.3 → 1.4 → 1.9 → 1.5 → 1.6`

**Why Story 1.9 is on critical path:**
- Production deployment (Story 1.6) **requires** group support (P0 feature)
- Cannot launch production without this core differentiating feature
- Deploying private-only, then adding groups later = painful production data migration
- Schema changes easier with small user base

**Velocity Assumptions:**
- Team capacity: 18-20 SP per 2-week sprint (solo developer or small team)
- Total epic: ~86 SP = ~4.5 sprints (9 weeks)
- Buffer: Add 20% for bug fixes, documentation = ~11 weeks total
- Story 1.10 is optional and not counted in main timeline

---
