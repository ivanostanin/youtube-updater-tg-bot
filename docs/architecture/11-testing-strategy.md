# 11. Testing Strategy

## 11.1 Integration with Existing Tests

**Existing Test Framework:** pytest 8.4.2 with pytest-asyncio 1.2.0 for async test support

**Test Organization:**
- `tests/unit/` for isolated component tests (services, repositories, utilities)
- `tests/integration/` for multi-component workflows (subscription flow, webhook processing)
- `tests/fixtures/` for shared test data and mocks

**Coverage Requirements:** 70%+ coverage for core business logic (handlers, services, repositories)

## 11.2 New Testing Requirements

### 11.2.1 Unit Tests for New Components

**Framework:** pytest with pytest-asyncio, pytest-mock for mocking
**Location:** `tests/unit/services/`, `tests/unit/repositories/`
**Coverage Target:** 80%+ for new service layer (ACLService, PreferenceManager, etc.)
**Integration with Existing:** Use shared fixtures from `conftest.py` (mock database session, mock Telegram bot)

**Key Test Cases:**
- `test_acl_service.py`: Admin verification, permission checks, error handling (non-admin user, API timeout)
- `test_preference_manager.py`: Get/set preferences, default value handling, JSON serialization
- `test_deletion_scheduler.py`: Schedule deletion, process queue, retry logic for failed deletions
- `test_history_service.py`: Filtering, pagination, search functionality

### 11.2.2 Integration Tests

**Scope:** End-to-end workflows crossing multiple components

**Existing System Verification:** Run existing subscription flow tests after enhancements to ensure backward compatibility

**New Feature Testing:**
- Group subscription with admin verification flow
- Auto-deletion scheduling and execution
- Preference persistence across sessions
- LLM summary generation with cache hit/miss scenarios (Phase 3)

**Test Environment:**
- In-memory SQLite database (`sqlite:///:memory:`) for fast, isolated tests
- Mock Telegram Bot API responses using pytest-mock or respx
- Mock YouTube API and PubSubHubbub responses
- Async fixtures for database session initialization

## 11.3 Regression Testing

**Existing Feature Verification:**
- All current commands (`/start`, `/subscribe`, `/list`, `/unsubscribe`) function identically
- Webhook processing for YouTube notifications unchanged
- Existing subscriptions remain valid after migration

**Automated Regression Suite:**
- Snapshot testing for bot message formats (ensure formatting consistency)
- Database query tests to verify existing queries still work after schema changes

**Manual Testing Requirements:**
- Full user journey test in staging (subscribe → receive notification → unsubscribe)
- Multi-user group testing (admin vs. non-admin permissions)

---
