"""Policy-gated, idempotent planning for alarm repeats and escalations."""

from __future__ import annotations

from datetime import datetime

from .adapters import DeliveryRequest
from .alarm_lifecycle import AlarmLifecycleStore, AlarmRecord
from .delivery_store import DeliveryStore, PolicySuppressedError
from .policies import PolicyStore


class RepeatEscalationDeliveryPlanner:
    """Create persistent delivery jobs without invoking any adapter."""

    def __init__(self, alarm_store: AlarmLifecycleStore, delivery_store: DeliveryStore, policy_store: PolicyStore):
        self.alarm_store = alarm_store
        self.delivery_store = delivery_store
        self.policy_store = policy_store

    async def async_plan_due(self, *, now: datetime) -> dict[str, list[dict]]:
        """Advance due state and enqueue each recipient/channel once."""
        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("timestamp must be timezone-aware")
        repeats = await self.alarm_store.async_due_repeats(now=now)
        escalations = await self.alarm_store.async_due_escalations(now=now)
        planned: list[dict] = []
        suppressed: list[dict] = []
        for alarm in repeats:
            await self._plan_alarm(alarm, "repeat", alarm.repeat_count, alarm.repeat_recipient_ids, alarm.repeat_channel_ids, now, planned, suppressed)
        for alarm in escalations:
            stage = alarm.escalation_stages[alarm.escalation_level - 1] if alarm.escalation_level else {}
            recipients = tuple(str(item) for item in stage.get("recipient_ids", alarm.repeat_recipient_ids))
            channels = tuple(str(item) for item in stage.get("channel_ids", alarm.repeat_channel_ids))
            await self._plan_alarm(alarm, "escalation", alarm.escalation_level, recipients, channels, now, planned, suppressed)
        return {"planned": planned, "suppressed": suppressed}

    async def _plan_alarm(self, alarm: AlarmRecord, kind: str, sequence: int, recipients: tuple[str, ...], channels: tuple[str, ...], now: datetime, planned: list[dict], suppressed: list[dict]) -> None:
        for recipient_id in recipients:
            for channel_id in channels:
                key = f"alarm:{alarm.alarm_id}:{kind}:{sequence}:{recipient_id}:{channel_id}"
                request = DeliveryRequest(
                    attempt_id=key,
                    recipient_id=recipient_id,
                    title=f"{alarm.friendly_name or alarm.entity_id} ({kind})",
                    message=f"{alarm.friendly_name or alarm.entity_id}: {alarm.current_state or 'Alarm aktiv'}",
                    payload={"alarm_id": alarm.alarm_id, "rule_id": alarm.rule_id, "sequence": sequence, "kind": kind},
                )
                policy_request = {"rule_id": alarm.rule_id, "alarm_id": alarm.alarm_id, "alarm_state": alarm.alarm_state, "priority": alarm.priority, "entity_id": alarm.entity_id, "category": alarm.category}
                try:
                    job = await self.delivery_store.async_enqueue(request, idempotency_key=key, channel_id=channel_id, alarm_id=alarm.alarm_id, policy_store=self.policy_store, policy_request=policy_request, now=now)
                    planned.append({"alarm_id": alarm.alarm_id, "kind": kind, "sequence": sequence, "recipient_id": recipient_id, "channel_id": channel_id, "attempt_id": job.attempt_id, "state": job.state, "adapter_called": False})
                except PolicySuppressedError as error:
                    suppressed.append({"alarm_id": alarm.alarm_id, "kind": kind, "sequence": sequence, "recipient_id": recipient_id, "channel_id": channel_id, "reason": error.decision.reason_code, "adapter_called": False})
