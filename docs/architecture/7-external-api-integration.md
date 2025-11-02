# 7. External API Integration

## 7.1 OpenAI API (Phase 3)

**Purpose:** Generate video transcript summaries using GPT-4 or GPT-4-Turbo
**Documentation:** https://platform.openai.com/docs/api-reference
**Base URL:** https://api.openai.com/v1
**Authentication:** Bearer token via OPENAI_API_KEY environment variable
**Integration Method:** Official OpenAI Python SDK with async support; httpx as underlying client

**Key Endpoints Used:**
- `POST /chat/completions` - Generate summary from transcript text
- `GET /models` - List available models for cost optimization

**Error Handling:**
- **Rate limit (429):** Exponential backoff with max 3 retries, fallback to Anthropic
- **Quota exceeded (402):** Switch to Anthropic provider, notify user of degraded service
- **Timeout:** 30s timeout with retry, cache partial responses
- **Invalid request (400):** Log error, return graceful error message to user

## 7.2 Anthropic API (Phase 3)

**Purpose:** Alternative LLM provider for video summaries; longer context window, lower cost
**Documentation:** https://docs.anthropic.com/claude/reference
**Base URL:** https://api.anthropic.com/v1
**Authentication:** API key via ANTHROPIC_API_KEY environment variable
**Integration Method:** Official Anthropic Python SDK with async support

**Key Endpoints Used:**
- `POST /messages` - Generate summary using Claude 3 Opus/Sonnet

**Error Handling:**
- **Rate limit (429):** Exponential backoff, if both providers rate-limited, queue request for later
- **Overloaded (529):** Retry with exponential backoff (5s, 10s, 20s)
- **Invalid request (400):** Log detailed error, return user-friendly message

## 7.3 YouTube Transcript API (Phase 3 - Third-Party Library)

**Purpose:** Retrieve video transcripts/captions for summarization
**Documentation:** https://github.com/jdepoix/youtube-transcript-api
**Base URL:** N/A (library handles YouTube internal APIs)
**Authentication:** None (public API)
**Integration Method:** youtube-transcript-api Python library with async wrapper

**Error Handling:**
- **Transcript unavailable:** Gracefully notify user that summary cannot be generated (video has no captions)
- **Private video:** Return error message indicating transcript access denied
- **Network errors:** Retry with exponential backoff

---
