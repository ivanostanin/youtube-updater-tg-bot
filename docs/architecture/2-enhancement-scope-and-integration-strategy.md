# 2. Enhancement Scope and Integration Strategy

## 2.1 Enhancement Overview

**Enhancement Type:** Multi-phase brownfield feature expansion with architectural improvements

**Scope:** This enhancement encompasses three major feature areas building on the existing v0.1.0 foundation:

### 2.1.1 Phase 1 - Foundation Improvements (Weeks 1-2)

- Database migration framework (Alembic integration)
- Admin access control for groups/channels (Telegram permission verification)
- Configurable webhook URL (environment-based configuration)
- Enhanced notification formatting (thumbnails, rich embeds)
- Comprehensive test suite (pytest with 70%+ coverage target)

### 2.1.2 Phase 2 - User Experience Enhancements (Weeks 3-5)

- Auto-deletion timers for notifications (1-7 day configurable retention)
- Update history management (searchable, filterable notification logs)
- Group/channel multi-context support (separate subscription lists per chat)
- Notification customization (templates, quiet hours, priority channels)

### 2.1.3 Phase 3 - Premium Features (Weeks 6-8+)

- LLM-powered video transcript summaries (OpenAI/Anthropic integration)
- Voice message narration (TTS synthesis)
- Token-based rate limiting with caching
- PostgreSQL migration path for scalability

**Integration Impact:** Medium-High - Enhancements require database schema changes, new service components, external API integrations, and refactoring of notification delivery pipeline. Existing core functionality (subscribe, list, unsubscribe, webhook handling) remains intact with backward compatibility.

## 2.2 Integration Approach

### 2.2.1 Code Integration Strategy

- **Extend Repository Pattern:** New repositories (ChatRepository, PreferenceRepository, HistoryRepository) will follow existing UserRepository, ChannelRepository patterns in `src/database/repository.py`
- **Service Layer Introduction:** Create `src/services/` directory for business logic (ACL verification, auto-deletion scheduler, premium feature orchestration) to separate concerns from bot handlers
- **Minimal Handler Refactoring:** Existing BotHandlers class in `src/bot/handlers.py` will gain new command methods but maintain current command structure and message handling patterns
- **Backward Compatible Changes:** All existing database models and API contracts remain unchanged; new features add tables/columns without breaking existing subscriptions

### 2.2.2 Database Integration

- **Alembic Migrations:** Introduce `migrations/` directory with version control for schema changes, enabling safe rollback and upgrade paths
- **New Tables:** Add `chats` (group/channel context), `preferences` (user/chat settings), `deletion_queue` (scheduled message cleanup), `transcript_cache` (LLM response caching)
- **Modified Tables:** Add nullable columns to existing `subscriptions` (chat_id FK), `notifications` (deletion_scheduled_at, thumbnail_url)
- **Zero-Downtime Strategy:** Migrations will be additive-only in Phase 1; data backfills run post-deployment via background jobs

### 2.2.3 API Integration

- **Internal APIs:** New service methods will expose clean interfaces to bot handlers (e.g., `ACLService.verify_admin()`, `DeletionService.schedule_cleanup()`)
- **External APIs:** Integrate Telegram getChatMember for ACL (existing httpx client), OpenAI/Anthropic for summaries (new httpx client in `src/premium/llm_client.py`)
- **Webhook Endpoints:** Maintain existing `/webhook/youtube` and `/health`; add `/webhook/telegram` for potential future Telegram webhook mode (optional)

### 2.2.4 UI Integration

All UI is Telegram-native via bot messages and inline keyboards; enhancements will add new inline keyboard options (e.g., "Schedule deletion", "Get AI summary") and command responses.

## 2.3 Compatibility Requirements

### 2.3.1 Existing API Compatibility

- All current bot commands (`/start`, `/subscribe`, `/list`, `/unsubscribe`, `/help`) maintain identical interfaces and response formats
- Internal repository methods retain existing signatures; new methods added alongside
- PubSubHubbub webhook handler signature unchanged; processing logic extended

### 2.3.2 Database Schema Compatibility

- Alembic migrations ensure zero data loss during upgrades
- Existing tables (`users`, `youtube_channels`, `subscriptions`, `videos`, `notifications`) keep current columns with original types
- New columns nullable by default to support existing rows
- Downgrade paths provided for safe rollback

### 2.3.3 UI/UX Consistency

- Message formatting maintains current Markdown style
- Inline keyboards follow existing button labeling conventions (emoji + text)
- Error messages preserve friendly, informative tone
- New features accessible via new commands (e.g., `/history`, `/settings`) without disrupting current workflows

### 2.3.4 Performance Impact

- Admin ACL checks add ~100-200ms latency per group/channel command (single Telegram API call)
- Auto-deletion scheduler runs background job every 5 minutes (minimal impact)
- LLM summaries are opt-in and cached (no impact on standard notification delivery)
- Database indexes added for new query patterns (chat_id, scheduled timestamps) to maintain <500ms command response times


## 2.4  Rationale & Key Decisions:

  Why This Phased Approach:
  1. Risk Mitigation: Phase 1 establishes critical infrastructure (migrations, ACL) before adding user-facing features, reducing deployment risk
  2. User Value Delivery: Phase 2 delivers high-impact UX improvements without external dependencies, enabling faster iteration
  3. Cost Management: Phase 3's premium features are gated behind optional LLM integration, allowing validation of free-tier offerings first

  Integration Strategy Choices:
  - Service Layer Introduction: Your current code has handlers directly calling repositories. I'm proposing a src/services/ layer to encapsulate multi-step business logic (e.g., ACL + subscription
  creation) and keep handlers thin. Trade-off: Adds abstraction layer but improves testability and maintainability.
  - Repository Pattern Extension: Following your existing pattern in repository.py rather than introducing ORM repositories or DAOs ensures consistency with current codebase style
  - Additive Database Changes: By making all new columns nullable and using separate tables for new features, we avoid complex data migrations and maintain rollback safety

  Key Assumptions:
  - The dual-threaded model (bot polling + webhook server) will persist through enhancements
  - Existing subscriptions are all personal DM subscriptions (no chat_id), allowing safe migration to multi-context model
  - Users prefer backward-compatible upgrades over breaking changes requiring re-subscription

  Areas Needing Validation:
  - Should admin ACL checks be synchronous (blocking command) or async with provisional subscription pending admin approval?
  - Is your production deployment using the hardcoded webhook URL, or will environment-based configuration require migration coordination?
  - What's your preference for premium feature access control: separate bot instance, in-app purchase flow, or manual allowlist?
