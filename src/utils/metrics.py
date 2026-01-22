"""Prometheus metrics helpers for application monitoring."""

from __future__ import annotations

from prometheus_client import Counter, Gauge, Histogram


_DEFAULT_MODE = "unknown"

# Counter tracking PubSub verification challenges handled by the bot.
WEBHOOK_VERIFICATION_CHALLENGES = Counter(
    "pubsub_verification_challenges_total",
    "Number of PubSub verification challenges processed by mode and result.",
    ("mode", "result"),
)

# Counter summarizing outcomes of lease refresher runs.
WEBHOOK_LEASE_REFRESH_TOTAL = Counter(
    "pubsub_lease_refresh_total",
    "Lease refresh attempts grouped by result (attempt, success, failure, skipped).",
    ("result",),
)

# Channel linking/selection metrics to observe DM onboarding health.
CHANNEL_LINK_TOTAL = Counter(
    "channel_link_total",
    "Channel linking attempts grouped by outcome (success, denied, bot_missing, error).",
    ("result",),
)
CHANNEL_SELECTION_TOTAL = Counter(
    "channel_selection_total",
    "DM channel selection attempts grouped by outcome (selected, cleared, denied, expired, error).",
    ("result",),
)
CHANNEL_UNLINK_TOTAL = Counter(
    "channel_unlink_total",
    "DM channel unlink attempts grouped by outcome (prompt, success, cancelled, denied, error).",
    ("result",),
)

# Story 1.5 metrics
TELEGRAM_COMMANDS_TOTAL = Counter(
    "telegram_commands_total",
    "Total number of Telegram bot commands executed.",
    ("command", "status"),
)

WEBHOOK_NOTIFICATIONS_RECEIVED_TOTAL = Counter(
    "webhook_notifications_received_total",
    "Total number of webhook notifications received from YouTube.",
)

YOUTUBE_API_CALLS_TOTAL = Counter(
    "youtube_api_calls_total",
    "Total number of YouTube API calls made.",
    ("status",),
)

SUBSCRIPTION_COUNT = Gauge(
    "subscription_count",
    "Current number of active YouTube channel subscriptions.",
)

ACTIVE_USERS_COUNT = Gauge(
    "active_users_count",
    "Current number of active users.",
)

NOTIFICATION_DELIVERY_LATENCY_SECONDS = Histogram(
    "notification_delivery_latency_seconds",
    "Time taken to deliver notifications to Telegram users.",
    buckets=(0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 10.0, float("inf")),
)


def _normalize_mode(mode: str | None) -> str:
    normalized = (mode or "").strip().lower()
    return normalized or _DEFAULT_MODE


def record_webhook_verification(mode: str | None, result: str) -> None:
    """Increment the verification counter for the provided mode/result."""
    WEBHOOK_VERIFICATION_CHALLENGES.labels(
        mode=_normalize_mode(mode),
        result=result,
    ).inc()


def record_lease_refresh(result: str) -> None:
    """Increment the lease refresh counter for the provided result."""
    WEBHOOK_LEASE_REFRESH_TOTAL.labels(result=result).inc()


def record_channel_link(result: str) -> None:
    """Increment the link counter for the provided outcome."""
    CHANNEL_LINK_TOTAL.labels(result=result).inc()


def record_channel_selection(result: str) -> None:
    """Increment the channel selection counter for the provided outcome."""
    CHANNEL_SELECTION_TOTAL.labels(result=result).inc()


def record_channel_unlink(result: str) -> None:
    """Increment the channel unlink counter for the provided outcome."""
    CHANNEL_UNLINK_TOTAL.labels(result=result).inc()


def record_command(command: str, status: str = "success") -> None:
    """Increment the command counter for the provided command and status."""
    TELEGRAM_COMMANDS_TOTAL.labels(command=command, status=status).inc()


def record_webhook_notification() -> None:
    """Increment the webhook notification counter."""
    WEBHOOK_NOTIFICATIONS_RECEIVED_TOTAL.inc()


def record_youtube_api_call(status: str = "success") -> None:
    """Increment the YouTube API call counter for the provided status."""
    YOUTUBE_API_CALLS_TOTAL.labels(status=status).inc()


def set_subscription_count(count: int) -> None:
    """Set the current subscription count gauge."""
    SUBSCRIPTION_COUNT.set(count)


def set_active_users_count(count: int) -> None:
    """Set the current active users count gauge."""
    ACTIVE_USERS_COUNT.set(count)


def observe_notification_latency(latency_seconds: float) -> None:
    """Record a notification delivery latency observation."""
    NOTIFICATION_DELIVERY_LATENCY_SECONDS.observe(latency_seconds)


def reset_pubsub_metrics() -> None:
    """Clear recorded label values for deterministic tests."""
    WEBHOOK_VERIFICATION_CHALLENGES.clear()
    WEBHOOK_LEASE_REFRESH_TOTAL.clear()
    CHANNEL_LINK_TOTAL.clear()
    CHANNEL_SELECTION_TOTAL.clear()
    CHANNEL_UNLINK_TOTAL.clear()


def reset_all_metrics() -> None:
    """Clear all metrics for deterministic tests."""
    reset_pubsub_metrics()
    TELEGRAM_COMMANDS_TOTAL.clear()
    WEBHOOK_NOTIFICATIONS_RECEIVED_TOTAL._value.set(0)
    YOUTUBE_API_CALLS_TOTAL.clear()
    SUBSCRIPTION_COUNT.set(0)
    ACTIVE_USERS_COUNT.set(0)
