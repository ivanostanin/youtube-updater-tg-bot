# 10. Coding Standards

## 10.1 Existing Standards Compliance

**Code Style:**
- PEP 8 with 100-character line length (configured in `pyproject.toml`)
- ruff for linting and formatting (replaces black + flake8 + isort)
- Double-quote strings, 4-space indentation
- Async/await preferred over callbacks

**Linting Rules:**
- **ruff select:** E (pycodestyle errors), W (warnings), F (pyflakes), I (isort), N (pep8-naming), UP (pyupgrade), B (flake8-bugbear), C4 (comprehensions), SIM (simplify), TID (tidy-imports)
- **ruff ignore:** E501 (line too long - handled by formatter), E712 (avoid == True), TID252 (relative imports)

**Testing Patterns:**
- pytest with async support (pytest-asyncio)
- Fixtures for database session, mock API clients
- Target: 70%+ code coverage for core logic
- Test organization: `tests/unit/` and `tests/integration/` mirroring `src/` structure

**Documentation Style:**
- Docstrings for all public functions/methods (Google style)
- Type hints for all function signatures (mypy strict mode)
- Inline comments for complex logic only (self-documenting code preferred)
- README.md for quickstart, CLAUDE.md for developer guidance

## 10.2 Enhancement-Specific Standards

- **Service Layer Typing:** All service methods must include full type hints with `-> ReturnType` annotations
- **Repository Transactions:** Use `async with session.begin()` for multi-statement transactions; avoid auto-commit
- **Error Handling:** Custom exception classes for domain errors (ACLPermissionDenied, QuotaExceeded); catch and log at handler level
- **Async Consistency:** All I/O operations (database, HTTP, file) must be async; no blocking calls in event loop

## 10.3 Critical Integration Rules

- **Existing API Compatibility:** New command handlers follow existing naming pattern (`{command}_command(update, context)`); existing commands unchanged
- **Database Integration:** All new repositories extend BaseRepository pattern (if created); use async session from `AsyncSessionLocal()`
- **Error Handling:** Maintain existing error handler pattern (log + notify user); extend with service-specific error types
- **Logging Consistency:** Use `logging.getLogger(__name__)` per module; structured logging with context (user_id, chat_id, video_id)

---
