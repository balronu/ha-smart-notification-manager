"""Authorized delivery orchestration around persistent jobs and adapters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from .adapters import ChannelAdapter, DeliveryAuthorizationError, DeliveryRequest, DeliveryResult
from .delivery_store import DeliveryJob, DeliveryStore
from .policies import PolicyStore


class DeliveryService:
    """Run one technical delivery only after an explicit authorization flag."""

    def __init__(self, store: DeliveryStore, policy_store: PolicyStore | None = None) -> None:
        self.store = store
        self.policy_store = policy_store

    async def async_deliver(
        self,
        request: DeliveryRequest,
        *,
        channel_id: str,
        idempotency_key: str,
        adapter: ChannelAdapter,
        recipient: dict[str, Any],
        authorized: bool = False,
        now: datetime | None = None,
    ) -> DeliveryJob:
        if not authorized:
            raise DeliveryAuthorizationError("Explizite Versandbestätigung erforderlich")
        timestamp = now or datetime.now(UTC)
        job = await self.store.async_enqueue(request, idempotency_key=idempotency_key, channel_id=channel_id, alarm_id=request.payload.get("alarm_id"), policy_store=self.policy_store, policy_request=request.payload.get("policy_request"), now=timestamp)
        if job.state in {"accepted", "delivered", "simulated", "failed"}:
            return job
        claimed = await self.store.async_claim_due(now=timestamp, attempt_id=job.attempt_id)
        if claimed is None or claimed.attempt_id != job.attempt_id:
            return job
        errors = await adapter.async_validate(recipient)
        if errors:
            return await self.store.async_record_result(
                job.attempt_id,
                DeliveryResult(status="failed", error_code="invalid_target", error_message="; ".join(errors)),
                now=timestamp,
            )
        try:
            result = await adapter.async_send(request)
        except Exception as err:  # noqa: BLE001 - adapter boundary must persist provider failures
            result = DeliveryResult(status="failed", error_code="provider_error", error_message=str(err))
        return await self.store.async_record_result(job.attempt_id, result, now=timestamp)
