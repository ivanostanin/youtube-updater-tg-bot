from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ..database.repository import ChannelRepository, LeaseRenewalCandidate
from ..utils.logging import get_logger, log_context, new_request_id
from .constants import DEFAULT_PUBSUB_LEASE_SECONDS
from .pubsub import PubSubManager


logger = get_logger(__name__)


class WebhookLeaseRefresher:
    """Background worker that renews expiring PubSub leases."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        *,
        webhook_callback_url: str,
        renewal_threshold_seconds: int,
        default_lease_seconds: int = DEFAULT_PUBSUB_LEASE_SECONDS,
        max_attempts: int = 3,
        retry_delay: float = 1.5,
        batch_limit: int | None = 50,
    ) -> None:
        self._session_factory = session_factory
        self._webhook_callback_url = webhook_callback_url
        self._renewal_threshold = max(renewal_threshold_seconds, 300)
        self._default_lease_seconds = max(default_lease_seconds, 60)
        self._max_attempts = max(1, max_attempts)
        self._retry_delay = max(0.1, retry_delay)
        self._batch_limit = batch_limit

    async def run(self) -> None:
        """Identify channels with expiring leases and renew them sequentially."""
        request_id = new_request_id()
        operation = "webhook.lease_refresher.run"
        now = datetime.now(UTC)
        threshold = now + timedelta(seconds=self._renewal_threshold)

        async with self._session_factory() as session:
            channel_repo = ChannelRepository(session)
            candidates = await channel_repo.get_channels_ready_for_lease_renewal(
                threshold=threshold,
                limit=self._batch_limit,
                request_id=request_id,
            )

            if not candidates:
                logger.debug(
                    "Lease refresher found no expiring channels",
                    extra=log_context(
                        request_id=request_id,
                        operation=operation,
                        meta_threshold=threshold.isoformat(),
                    ),
                )
                return

            logger.info(
                "Lease refresher renewing channels",
                extra=log_context(
                    request_id=request_id,
                    operation=operation,
                    meta_candidate_count=len(candidates),
                    meta_threshold=threshold.isoformat(),
                ),
            )

            manager = PubSubManager(self._webhook_callback_url)
            try:
                for candidate in candidates:
                    await self._renew_single_channel(
                        channel_repo,
                        candidate,
                        manager,
                        request_id=request_id,
                    )
            finally:
                await manager.close()

    async def _renew_single_channel(
        self,
        channel_repo: ChannelRepository,
        candidate: LeaseRenewalCandidate,
        manager: PubSubManager,
        *,
        request_id: str,
    ) -> None:
        operation = "webhook.lease_refresher.renew_channel"
        lease_seconds = candidate.webhook_lease_seconds or self._default_lease_seconds

        attempt = 0
        while attempt < self._max_attempts:
            attempt += 1
            success = await manager.subscribe_to_channel(candidate.channel_id)
            if success:
                now = datetime.now(UTC)
                expires_at = now + timedelta(seconds=lease_seconds)
                recorded = await channel_repo.record_webhook_verification(
                    channel_id=candidate.channel_id,
                    callback_url=self._webhook_callback_url,
                    lease_seconds=lease_seconds,
                    lease_expires_at=expires_at,
                    last_verified_at=now,
                    request_id=request_id,
                )
                if recorded:
                    logger.info(
                        "Renewed webhook lease for channel",
                        extra=log_context(
                            request_id=request_id,
                            operation=operation,
                            channel_id=candidate.channel_id,
                            meta_subscriber_count=candidate.subscriber_count,
                            meta_attempt=attempt,
                            meta_lease_seconds=lease_seconds,
                            meta_expires_at=expires_at.isoformat(),
                        ),
                    )
                else:
                    logger.warning(
                        "Lease refreshed but channel metadata missing; skipping persistence",
                        extra=log_context(
                            request_id=request_id,
                            operation=operation,
                            channel_id=candidate.channel_id,
                        ),
                    )
                return

            await asyncio.sleep(self._retry_delay * attempt)

        logger.error(
            "Failed to renew webhook lease after retries",
            extra=log_context(
                request_id=request_id,
                operation=operation,
                channel_id=candidate.channel_id,
                meta_attempts=self._max_attempts,
                meta_last_error="hub renewal failed",
            ),
        )
