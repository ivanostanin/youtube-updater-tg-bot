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


def reset_pubsub_metrics() -> None:
    """Clear recorded label values for deterministic tests."""
    WEBHOOK_VERIFICATION_CHALLENGES.clear()
    WEBHOOK_LEASE_REFRESH_TOTAL.clear()
