"""Prometheus metrics helpers for webhook lease instrumentation."""

from __future__ import annotations

from prometheus_client import Counter


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


def reset_pubsub_metrics() -> None:
    """Clear recorded label values for deterministic tests."""
    WEBHOOK_VERIFICATION_CHALLENGES.clear()
    WEBHOOK_LEASE_REFRESH_TOTAL.clear()
    CHANNEL_LINK_TOTAL.clear()
    CHANNEL_SELECTION_TOTAL.clear()
    CHANNEL_UNLINK_TOTAL.clear()
