# Channel Support Runbook

This note explains how operators can validate and monitor the DM-only Telegram channel onboarding flow introduced in Story 1.15.

## 1. Pre-checks

1. Verify the bot is running with the correct environment variables:
   - `TELEGRAM_BOT_TOKEN` points to the production bot.
   - `DM_CHANNEL_CONTEXT_TTL_MINUTES` is set to the expected policy (default 60 minutes).
2. Ensure the database has applied migration `20250305_channel_admin_dm_context`.
3. Confirm the locale catalogs include the new `channel_link` and `channel_select` keys (run `pytest tests/unit/test_handlers.py -k channel_link` if in doubt).

## 2. Manual Verification Steps

The following flow keeps all sensitive prompts inside a DM between the admin and the bot:

1. **Link a channel**
   - In a DM, run `/channel_link @mychannel`.
   - For private/invite-only channels, forward any recent post from the channel to the DM, reply with `/channel_link`, and confirm the bot resolves the hidden chat ID.
   - The bot should confirm success and mention that DM commands now target the channel for `DM_CHANNEL_CONTEXT_TTL_MINUTES` minutes.
   - Check the `channel_admin_links` table for the new record and ensure the DM chat row references `active_channel_chat_id`.
2. **Select or switch a channel**
   - Run `/channel_select` in the DM to view the inline keyboard.
   - Pick a linked channel and verify the bot acknowledges the selection.
   - Optional: choose “Use this DM” to clear the context.
3. **Subscribe from DM context**
   - Still in the DM, run `/subscribe <YouTube URL>`.
   - Confirm the success message mentions the targeted channel and the `subscriptions` row references the channel chat, not the admin’s private chat.
4. **List/unsubscribe**
   - `/list` and `/unsubscribe` should mention the channel being managed. Unsubscribing via inline keyboard should clean up the PubSub webhook when the last subscriber leaves.

## 3. Monitoring & Metrics

Two Prometheus counters are exposed via `src/utils/metrics.py`:

| Metric | Labels | Description |
|--------|--------|-------------|
| `channel_link_total` | `result` (`success`, `denied`, `bot_missing`, `error`) | Tracks DM linking attempts |
| `channel_selection_total` | `result` (`selected`, `cleared`, `denied`, `expired`, `bot_missing`, `error`, `empty`) | Tracks `/channel_select` outcomes |

Add these series to the existing alerting dashboards so spikes in `denied`/`error` are visible alongside PubSub health.

## 4. Troubleshooting Tips

- If admins report “missing permissions”, double-check that the bot is added as a channel administrator with *Post*, *Edit*, and *Delete* rights.
- If `/channel_link` says it needs more info for a private channel, remind the admin to forward a channel message (or reply to one) before running the command so the bot can read the opaque chat ID.
- When `/channel_select` shows no options, verify `channel_admin_links.revoked_at` is `NULL` and the admin still has Telegram privileges.
- Context expirations happen automatically when the TTL elapses. Users can simply rerun `/channel_select` to continue working.
- Use `channel_link_total{result="error"}` spikes as a signal to inspect Telegram API rate limits or connectivity.
