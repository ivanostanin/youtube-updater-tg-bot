# 6. API Design and Integration

## 6.1 API Integration Strategy

**Strategy:** Bot command API extends existing Telegram Bot API command handlers with new commands (`/history`, `/settings`, `/summary`) while maintaining backward compatibility. Internal service APIs follow repository pattern with async interfaces. External integrations use httpx with retry logic and circuit breakers.

**Authentication:**
- **Telegram Bot API:** Token-based authentication via TELEGRAM_BOT_TOKEN environment variable (existing)
- **Admin Verification:** Session-based using Telegram's getChatMember API for group/channel operations (new)
- **Premium Features:** User allowlist stored in preferences table (Phase 3)

**Versioning:** No versioning required for bot commands (users always interact with latest). Internal service APIs follow semantic versioning for breaking changes.

## 6.2 New Bot Commands

### 6.2.1 /settings

**Method:** Telegram Bot Command
**Endpoint:** Command handler in `BotHandlers.settings_command()`
**Purpose:** Display and configure user/chat preferences (auto-deletion, quiet hours, notification format)
**Integration:** Uses PreferenceManager to retrieve/update settings; presents inline keyboard for configuration

**Request:**
```json
{
  "message": {
    "text": "/settings",
    "chat": {"id": 123456, "type": "private"},
    "from": {"id": 789, "username": "user"}
  }
}
```

**Response:**
```json
{
  "text": "⚙️ Your Settings\n\n• Auto-deletion: 3 days\n• Quiet hours: 22:00-08:00\n• Notification format: Rich\n\nChange a setting:",
  "reply_markup": {
    "inline_keyboard": [
      [{"text": "🗑️ Change auto-deletion", "callback_data": "set_deletion"}],
      [{"text": "🌙 Configure quiet hours", "callback_data": "set_quiet"}],
      [{"text": "📝 Notification format", "callback_data": "set_format"}]
    ]
  }
}
```

### 6.2.2 /history

**Method:** Telegram Bot Command
**Endpoint:** Command handler in `BotHandlers.history_command()`
**Purpose:** Retrieve notification history with filtering and pagination
**Integration:** Uses HistoryService to query notifications; supports filters via inline keyboard or command args

**Request:**
```json
{
  "message": {
    "text": "/history channel:UC_x5XG1OV2P6uZZ5FSM9Ttw",
    "chat": {"id": 123456, "type": "private"}
  }
}
```

**Response:**
```json
{
  "text": "📋 Notification History (Page 1/5)\n\n1. **Video Title** by Channel Name\n   📅 2025-11-01 14:32\n   🔗 https://youtube.com/watch?v=xyz\n\n2. **Another Video** by Channel Name\n   📅 2025-11-01 12:15\n   🔗 https://youtube.com/watch?v=abc",
  "reply_markup": {
    "inline_keyboard": [
      [{"text": "⬅️ Previous", "callback_data": "hist_p0"}, {"text": "Next ➡️", "callback_data": "hist_p2"}],
      [{"text": "🔍 Filter by channel", "callback_data": "hist_filter"}]
    ]
  }
}
```

### 6.2.3 /summary (Phase 3)

**Method:** Telegram Bot Command
**Endpoint:** Command handler in `BotHandlers.summary_command()`
**Purpose:** Generate AI-powered video transcript summary
**Integration:** Uses TranscriptService which delegates to LLMClient; cache-first strategy

**Request:**
```json
{
  "message": {
    "text": "/summary https://youtube.com/watch?v=xyz",
    "chat": {"id": 123456, "type": "private"}
  }
}
```

**Response:**
```json
{
  "text": "🤖 AI Summary\n\n**Video:** How to Build a Telegram Bot\n**Duration:** 15:32\n\n📝 Summary:\nThis tutorial covers the fundamentals of building a Telegram bot using Python. Key topics include:\n• Setting up the development environment\n• Implementing command handlers\n• Working with inline keyboards\n• Deploying to production\n\nThe presenter demonstrates practical examples and best practices for bot development.\n\n🎧 [Get voice narration]",
  "reply_markup": {
    "inline_keyboard": [
      [{"text": "🎧 Listen to summary", "callback_data": "tts_xyz"}]
    ]
  }
}
```

---
