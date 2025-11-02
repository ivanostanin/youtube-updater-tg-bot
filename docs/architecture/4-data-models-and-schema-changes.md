# 4. Data Models and Schema Changes

## 4.1 New Data Models

### 4.1.1 Chat

**Purpose:** Support multi-context subscriptions (personal DMs, groups, channels) with separate subscription lists per Telegram chat.

**Integration:** Extends the current user-centric subscription model to support group/channel contexts. Existing User model represents individual users; Chat model represents Telegram chat contexts where the bot operates.

**Key Attributes:**

- `id`: Integer - Primary key
- `chat_id`: String - Telegram chat ID (unique, indexed)
- `chat_type`: String - Type of chat ('private', 'group', 'supergroup', 'channel')
- `title`: String (nullable) - Chat title for groups/channels
- `created_at`: DateTime - Timestamp when chat was first registered
- `is_active`: Boolean - Soft delete flag for inactive chats

**Relationships:**

- **With Existing:** One-to-Many with Subscription (a chat has many subscriptions)
- **With New:** One-to-Many with Preference (a chat has preferences), One-to-Many with Notification (notifications sent to chat)

### 4.1.2 Preference

**Purpose:** Store user/chat-level preferences for notification customization, auto-deletion timers, quiet hours, and premium feature settings.

**Integration:** Decouples configuration from User and Chat models, allowing flexible preference expansion without schema migrations. Uses key-value storage with JSON data type for extensibility.

**Key Attributes:**

- `id`: Integer - Primary key
- `user_id`: Integer (nullable, FK to users.id) - User preference owner
- `chat_id`: Integer (nullable, FK to chats.id) - Chat preference owner (mutually exclusive with user_id)
- `preference_key`: String - Preference identifier ('auto_deletion_days', 'quiet_hours_start', 'notification_template', etc.)
- `preference_value`: Text/JSON - Preference value (stores JSON for complex types)
- `created_at`: DateTime - Timestamp when preference was set
- `updated_at`: DateTime - Last modification timestamp

**Relationships:**

- **With Existing:** Many-to-One with User (user has many preferences)
- **With New:** Many-to-One with Chat (chat has many preferences)

**Constraint:** CHECK constraint ensuring either user_id OR chat_id is set, not both.

### 4.1.3 DeletionQueue

**Purpose:** Track scheduled message deletions for auto-deletion timer feature. Background job processes this queue to delete expired notifications.

**Integration:** Links to existing Notification records. When auto-deletion is enabled, notification entries are added to this queue with scheduled deletion timestamps.

**Key Attributes:**

- `id`: Integer - Primary key
- `notification_id`: Integer (FK to notifications.id) - Target notification to delete
- `chat_id`: String - Telegram chat ID where message was sent
- `message_id`: String - Telegram message ID to delete
- `scheduled_for`: DateTime - When message should be deleted (indexed for job queries)
- `status`: String - Processing status ('pending', 'processing', 'completed', 'failed')
- `attempts`: Integer - Retry counter for failed deletions
- `created_at`: DateTime - When deletion was scheduled
- `processed_at`: DateTime (nullable) - When deletion was executed

**Relationships:**

- **With Existing:** One-to-One with Notification (deletion queue entry references notification)

### 4.1.4 TranscriptCache

**Purpose:** Cache LLM-generated video transcript summaries to reduce API costs and improve response times for premium features.

**Integration:** Links to existing Video records. Cache lookup occurs before LLM API calls; cache entries have TTL (e.g., 30 days) for freshness.

**Key Attributes:**

- `id`: Integer - Primary key
- `video_id`: Integer (FK to videos.id, unique) - Target video for cached summary
- `summary_text`: Text - Generated transcript summary
- `summary_language`: String - Language of summary (default 'en')
- `model_name`: String - LLM model used ('gpt-4-turbo', 'claude-3-opus', etc.)
- `token_count`: Integer - Total tokens used for generation (for billing tracking)
- `created_at`: DateTime - Cache entry creation time
- `expires_at`: DateTime (nullable) - Cache expiration timestamp (indexed)

**Relationships:**

- **With Existing:** One-to-One with Video (one cached summary per video)

## 4.2 Modified Existing Models

### 4.2.1 Subscription (Phase 1 Migration)

**Add:**
- `chat_id` (Integer, nullable, FK to chats.id) - Allows subscriptions to belong to chats instead of just users

**Migration Strategy:** Existing subscriptions remain user-only (user_id populated, chat_id NULL). New group/channel subscriptions use chat_id. Unique constraint updated to (user_id, channel_id, chat_id).

### 4.2.2 Notification (Phase 2 Migration)

**Add:**
- `chat_id_sent_to` (String, nullable) - Telegram chat ID where notification was sent (supports group notifications)
- `thumbnail_url` (String, nullable) - Cached thumbnail URL for rich notifications
- `auto_delete_enabled` (Boolean, default False) - Flag indicating if deletion is scheduled

## 4.3 Schema Integration Strategy

### 4.3.1 Database Changes Required

**New Tables:**
- `chats` (Phase 1)
- `preferences` (Phase 2)
- `deletion_queue` (Phase 2)
- `transcript_cache` (Phase 3)

**Modified Tables:**
- `subscriptions` - Add nullable chat_id FK (Phase 1)
- `notifications` - Add chat_id_sent_to, thumbnail_url, auto_delete_enabled columns (Phase 2)

**New Indexes:**
- `chats.chat_id` - Unique index for fast chat lookup
- `subscriptions.chat_id` - FK index for chat subscriptions query
- `deletion_queue.scheduled_for` - Index for scheduler job queries
- `deletion_queue.status` - Composite index (status, scheduled_for) for efficient pending deletions query
- `transcript_cache.video_id` - Unique index for cache lookup
- `transcript_cache.expires_at` - Index for TTL cleanup job

### 4.3.2 Migration Strategy

1. **Phase 1:** Alembic initialization + chats table creation + subscriptions.chat_id column addition (nullable, default NULL)
2. **Phase 2:** Add preferences, deletion_queue, and notifications columns via separate migrations
3. **Phase 3:** Add transcript_cache table
4. **Data Backfill:** For existing subscriptions, no backfill needed (remain user-only). For multi-context support, users re-subscribe in groups to create chat-level subscriptions.

### 4.3.3 Backward Compatibility

- All new columns are nullable to support existing rows without data loss
- Existing queries on User, YouTubeChannel, Video models remain unchanged
- Repository methods check for chat_id presence to determine subscription context (user vs. chat)
- Downgrade migrations provided to drop tables/columns cleanly for rollback scenarios
- Database abstraction via SQLAlchemy maintained for SQLite → PostgreSQL migration path


## 4.4  Rationale & Key Decisions:

  Why These Models:

  1. Chat Model Separation: Rather than extending User with chat-related fields, a separate Chat model maintains clear separation between individual users and group/channel contexts. This enables:
  (a) same user to have different subscriptions in DMs vs. groups, (b) group settings independent of individual members, (c) clean admin ACL checks (chat membership vs. user identity).
  2. Preference Key-Value Store: Using a flexible key-value table instead of adding columns to User/Chat prevents schema churn as new preferences are added. JSON storage allows complex preference
  types (e.g., quiet hours as {"start": "22:00", "end": "08:00"}). Trade-off: Requires JSON parsing vs. typed columns, but gains schema flexibility.
  3. DeletionQueue Separate Table: Auto-deletion could be handled via scheduled jobs querying Notification.created_at directly, but a dedicated queue table provides: (a) retry tracking for failed
  deletions, (b) status monitoring (pending/completed), (c) decoupling deletion logic from core notification model. Alternative Considered: Adding deletion_scheduled_at to Notification model, but
  rejected due to lack of retry/status tracking.
  4. TranscriptCache Denormalization: Caching summaries in database (vs. Redis-only) ensures cache survives Redis restarts and enables cost tracking via token_count aggregation. Trade-off: Larger
  database size, but simplified operations (no Redis dependency in development).

  Schema Evolution Approach:

  - Additive-Only Migrations (Phase 1-2): All changes add new tables/columns without modifying existing structures, minimizing migration risk
  - Nullable FKs: subscriptions.chat_id is nullable to preserve existing user-only subscriptions, with application logic handling context determination
  - Phased Rollout: Database changes precede feature implementation in each phase, allowing staged deployment and testing

  Key Assumptions:
  - Existing subscriptions (v0.1.0) are all personal DM subscriptions (no group/channel usage yet)
  - Auto-deletion is opt-in per user/chat (default disabled to preserve backward compatibility)
  - LLM summaries have 30-day cache TTL (balance between freshness and cost savings)

  Areas Needing Validation:
  - Should Subscription model support both user_id AND chat_id simultaneously (user subscribes for themselves within a group), or mutually exclusive (subscription is either personal OR group-level)?
  - Is 30-day transcript cache TTL appropriate, or should it be configurable/infinite (videos don't change)?
  - Should DeletionQueue track all notifications (audit trail) or only pending/failed (smaller table)?

---
