# 2. Requirements

## 2.1 Functional Requirements

### Core Subscription Management (Implemented)

**FR1:** The system SHALL accept YouTube URLs in multiple formats (channel by ID, channel by handle, video URL, short URL, playlist URL) and resolve them to canonical channel IDs using YouTube Data API v3.

**FR2:** The system SHALL store user-channel subscription relationships in a persistent database with unique constraints preventing duplicate subscriptions.

**FR3:** The system SHALL provide Telegram bot commands (`/start`, `/subscribe`, `/list`, `/unsubscribe`, `/help`) with inline keyboard support for interactive operations.

**FR4:** The system SHALL automatically register PubSubHubbub webhooks for YouTube channels when the first user subscribes, and unregister when the last user unsubscribes.

**FR5:** The system SHALL receive and parse Atom XML feed notifications from PubSubHubbub containing video upload events.

**FR6:** The system SHALL send formatted Telegram notifications to all subscribed users when new videos are published, including video title, channel name, thumbnail URL, and direct link.

**FR7:** The system SHALL support direct message processing, allowing users to send YouTube URLs without using the `/subscribe` command prefix.

### Phase 2 Requirements (Planned)

**FR8:** The system SHALL support auto-deletion of notifications after a configurable time period (1-7 days) per user preference.

**FR9:** The system SHALL maintain a searchable history of sent notifications with filtering by channel, date range, and keyword.

**FR10:** The system SHALL support Telegram group and channel subscriptions with admin-only configuration permissions (chat type detection, permission verification).

**FR11:** The system SHALL provide notification customization options including format templates and quiet hours configuration.

### Future Premium Features (Planned)

**FR12:** The system SHALL integrate with LLM APIs to generate video transcript summaries with token-based rate limiting and response caching.

**FR13:** The system SHALL support voice message narration of video summaries for accessibility.

## 2.2 Non-Functional Requirements

### Performance

**NFR1:** Bot command responses SHALL complete within 500ms (p95) for local operations (list, help, settings).

**NFR2:** YouTube URL resolution and subscription creation SHALL complete within 3 seconds (p95).

**NFR3:** Webhook notifications SHALL be processed and forwarded to Telegram within 60 seconds of video publication.

**NFR4:** The system SHALL support at least 10,000 concurrent subscriptions without performance degradation.

**NFR5:** Database queries SHALL use appropriate indexes on `telegram_id`, `channel_id`, `video_id`, and `chat_id` fields.

### Reliability & Availability

**NFR6:** The system SHALL maintain 99.9% uptime during production operation.

**NFR7:** Webhook registration failures SHALL be logged with ERROR severity and SHALL NOT prevent subscription creation (graceful degradation).

**NFR8:** Database operations SHALL use async session management with proper connection pooling and transaction handling.

**NFR9:** The application SHALL implement graceful shutdown, closing database connections and stopping bot polling cleanly on SIGTERM.

**NFR10:** Database backups SHALL run daily with 30-day retention using an S3-compatible object storage endpoint (OCI Object Storage by default, configurable for AWS S3 fallback).

### Security

**NFR11:** API credentials (Telegram token, YouTube API key, OCI object storage access/secret keys) SHALL be stored in environment variables or Kubernetes secrets, never committed to source code.

**NFR12:** All webhook endpoints SHALL require HTTPS in production environments.

**NFR13:** Input validation SHALL be applied to all user-provided URLs and commands to prevent injection attacks.

**NFR14:** Admin verification SHALL be enforced for group/channel configuration operations using Telegram's getChatMember API.

**NFR15:** Logs SHALL NOT contain sensitive information (full API tokens, user personal data beyond Telegram IDs).

### Scalability

**NFR16:** The system architecture SHALL support migration from SQLite to PostgreSQL without application code changes (SQLAlchemy abstraction maintained).

**NFR17:** Notification delivery SHALL be designed to support message queuing for high-volume scenarios (rate limit compliance).

**NFR18:** YouTube API calls SHALL be optimized to stay within the 10,000 units/day free tier quota through caching and webhook-based notifications.

### Maintainability

**NFR19:** Code SHALL follow PEP 8 style guidelines enforced by ruff with 100-character line length.

**NFR20:** All public functions and methods SHALL include type hints compatible with mypy strict mode.

**NFR21:** Unit test coverage SHALL exceed 70% for core business logic (bot handlers, YouTube API, webhook processing).

**NFR22:** All external API integrations SHALL implement proper error handling, retry logic, and structured logging.

**NFR23:** Database schema changes SHALL be managed through Alembic migrations with both upgrade and downgrade paths.

## 2.3 Compatibility Requirements

**CR1: Database Schema Compatibility**
Future schema migrations SHALL use Alembic and maintain backward compatibility. Existing tables (`users`, `youtube_channels`, `subscriptions`, `videos`, `notifications`) SHALL NOT have columns removed or data types changed without migration path. New `chats` table and subscription refactoring must preserve existing subscription data.

**CR2: Telegram Bot API Compatibility**
The bot SHALL remain compatible with Telegram Bot API v6+ and python-telegram-bot v20+. Message format changes SHALL NOT break existing user interactions. Inline keyboard callback data format must remain consistent.

**CR3: YouTube API Compatibility**
The system SHALL handle YouTube Data API v3 changes gracefully with appropriate error handling. Channel ID resolution SHALL support both legacy URL formats and new handle-based URLs (@username).

**CR4: PubSubHubbub Protocol Compatibility**
Webhook handling SHALL comply with PubSubHubbub 0.4 specification. Feed parsing SHALL support Atom XML format with feedparser library. Hub verification challenges must be handled correctly.

**CR5: Deployment Compatibility**
Docker images SHALL support linux/amd64 and linux/arm64 platforms. Kubernetes manifests SHALL be compatible with k8s v1.24+. Helm charts SHALL support both direct secrets and External Secrets Operator integration.
