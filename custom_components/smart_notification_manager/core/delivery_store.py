"""Persistent, idempotent technical delivery lifecycle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from .adapters import DeliveryRequest, DeliveryResult
from .policies import PolicyDecision, PolicyStore
from .repository import SQLiteRepository


@dataclass(frozen=True, slots=True)
class DeliveryJob:
    attempt_id: str
    alarm_id: str | None
    idempotency_key: str
    recipient_id: str
    channel_id: str
    state: str
    attempt_number: int
    next_attempt_at: datetime | None
    delivery_confirmed: bool
    payload: dict[str, Any]


class PolicySuppressedError(RuntimeError):
    """The policy boundary rejected creation of a delivery job."""

    def __init__(self, decision: PolicyDecision) -> None:
        super().__init__(decision.reason_de)
        self.decision = decision


def _parse_time(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


def _utc(value: datetime) -> str:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value.astimezone(UTC).isoformat()


class DeliveryStore:
    """Store one logical delivery job per idempotency key.

    Technical retries reuse the same row and are independent from alarm
    repetition/escalation. SQLite transactions serialize claims safely.
    """

    def __init__(self, repository: SQLiteRepository) -> None:
        self.repository = repository

    async def async_enqueue(self, request: DeliveryRequest, *, idempotency_key: str, channel_id: str, alarm_id: str | None = None, policy_store: PolicyStore | None = None, policy_request: dict[str, Any] | None = None, now: datetime | None = None) -> DeliveryJob:
        if not idempotency_key.strip():
            raise ValueError("idempotency key is required")
        timestamp = now or datetime.now(UTC)
        now_text = _utc(timestamp)
        payload = json.dumps({"title": request.title, "message": request.message, **request.payload}, ensure_ascii=False, sort_keys=True)

        def operation(connection):
            existing = connection.execute("SELECT * FROM delivery_attempts WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            if existing is not None:
                return _row_to_job(existing)
            if policy_store is not None:
                if policy_request is None:
                    raise ValueError("Policy-Entscheidung für regulären Versand erforderlich")
                decision = policy_store.decide_in_connection(connection, policy_request, now=timestamp)
                if decision.action != "allow":
                    return decision
            connection.execute(
                """INSERT INTO delivery_attempts
                (attempt_id, idempotency_key, alarm_id, recipient_id, channel_id, state, attempt_number, next_attempt_at, attempted_at, payload_json)
                VALUES (?, ?, ?, ?, ?, 'pending', 0, NULL, ?, ?)
                ON CONFLICT DO NOTHING""",
                (request.attempt_id, idempotency_key, alarm_id, request.recipient_id, channel_id, now_text, payload),
            )
            row = connection.execute("SELECT * FROM delivery_attempts WHERE idempotency_key = ?", (idempotency_key,)).fetchone()
            return _row_to_job(row)

        result = await self.repository.async_run(operation)
        if isinstance(result, PolicyDecision):
            raise PolicySuppressedError(result)
        return result

    async def async_claim_due(self, *, now: datetime, lease_seconds: int = 60, attempt_id: str | None = None) -> DeliveryJob | None:
        now_text = _utc(now)
        lease = _utc(now + timedelta(seconds=lease_seconds))

        def operation(connection):
            query = """SELECT attempt_id FROM delivery_attempts
                WHERE ((state IN ('pending', 'retry_scheduled') AND (next_attempt_at IS NULL OR next_attempt_at <= ?))
                   OR (state = 'in_progress' AND lease_until <= ?))
                ORDER BY COALESCE(next_attempt_at, attempted_at), attempt_id LIMIT 1"""
            params: tuple[Any, ...] = (now_text, now_text)
            if attempt_id is not None:
                query = query.replace("WHERE ", "WHERE attempt_id = ? AND ", 1)
                params = (attempt_id, *params)
            row = connection.execute(query, params).fetchone()
            if row is None:
                return None
            updated = connection.execute(
                "UPDATE delivery_attempts SET state='in_progress', lease_until=?, attempted_at=? WHERE attempt_id=? AND (state IN ('pending', 'retry_scheduled') OR (state='in_progress' AND lease_until <= ?))",
                (lease, now_text, row[0], now_text),
            )
            if updated.rowcount != 1:
                return None
            return _row_to_job(connection.execute("SELECT * FROM delivery_attempts WHERE attempt_id=?", (row[0],)).fetchone())

        return await self.repository.async_run(operation)

    async def async_record_result(
        self,
        attempt_id: str,
        result: DeliveryResult,
        *,
        now: datetime,
        max_attempts: int = 3,
        backoff_seconds: int = 30,
    ) -> DeliveryJob:
        if max_attempts < 1:
            raise ValueError("max_attempts must be positive")
        def operation(connection):
            row = connection.execute("SELECT * FROM delivery_attempts WHERE attempt_id=?", (attempt_id,)).fetchone()
            if row is None:
                raise ValueError("delivery job not found")
            next_number = int(row["attempt_number"]) + 1
            success = result.status in {"accepted", "delivered", "simulated"}
            if success:
                state = result.status
                next_time = None
            elif next_number < max_attempts:
                state = "retry_scheduled"
                next_time = _utc(now + timedelta(seconds=backoff_seconds * (2 ** (next_number - 1))))
            else:
                state = "failed"
                next_time = None
            connection.execute(
                """UPDATE delivery_attempts SET state=?, attempt_number=?, next_attempt_at=?, lease_until=NULL,
                provider_message_id=?, error_code=?, error_message=?, delivery_confirmed=? WHERE attempt_id=?""",
                (state, next_number, next_time, result.provider_message_id, result.error_code, result.error_message, int(result.delivery_confirmed), attempt_id),
            )
            return _row_to_job(connection.execute("SELECT * FROM delivery_attempts WHERE attempt_id=?", (attempt_id,)).fetchone())

        return await self.repository.async_run(operation)

    async def async_list(self) -> list[DeliveryJob]:
        return await self.repository.async_run(lambda connection: [_row_to_job(row) for row in connection.execute("SELECT * FROM delivery_attempts ORDER BY attempted_at, attempt_id")])

    async def async_cancel_pending_for_alarm(self, alarm_id: str) -> int:
        return await self.repository.async_run(lambda connection: connection.execute("UPDATE delivery_attempts SET state='suppressed',error_code='alarm_closed',error_message='Alarm beendet',next_attempt_at=NULL,lease_until=NULL WHERE alarm_id=? AND state IN ('pending','retry_scheduled')", (alarm_id,)).rowcount)


def _row_to_job(row: Any) -> DeliveryJob:
    return DeliveryJob(
        attempt_id=row["attempt_id"],
        alarm_id=row["alarm_id"],
        idempotency_key=row["idempotency_key"],
        recipient_id=row["recipient_id"],
        channel_id=row["channel_id"],
        state=row["state"],
        attempt_number=int(row["attempt_number"]),
        next_attempt_at=_parse_time(row["next_attempt_at"]),
        delivery_confirmed=bool(row["delivery_confirmed"]),
        payload=json.loads(row["payload_json"] or "{}"),
    )
