"""Validated identifiers and state models for the notification domain."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4


class AlarmState(StrEnum):
    ACTIVE = "active"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class DeliveryState(StrEnum):
    PENDING = "pending"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class EscalationState(StrEnum):
    IDLE = "idle"
    RUNNING = "running"
    COMPLETE = "complete"


def new_id() -> str:
    """Return a stable opaque identifier for a stored aggregate."""

    return str(uuid4())


def validate_id(value: str) -> str:
    """Validate an opaque UUID used by the foundation schema."""

    try:
        UUID(value)
    except (ValueError, AttributeError, TypeError) as err:
        raise ValueError("identifier must be a UUID") from err
    return value


@dataclass(frozen=True, slots=True)
class AlarmLifecycle:
    """Separate alarm, acknowledgement, delivery and escalation state."""

    alarm_id: str
    rule_id: str
    cause_key: str
    alarm_state: AlarmState = AlarmState.ACTIVE
    acknowledgement_state: str = "unacknowledged"
    delivery_state: DeliveryState = DeliveryState.PENDING
    escalation_state: EscalationState = EscalationState.IDLE
    closure_reason: str | None = None
    technical_error: str | None = None


@dataclass(frozen=True, slots=True)
class Rule:
    """Small transport-neutral rule record."""

    rule_id: str
    name: str
    category: str
    enabled: bool = True


def ensure_aware(value: datetime) -> datetime:
    """Reject naive timestamps at the domain boundary."""

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamps must be timezone-aware")
    return value

