"""Phase-1 engine boundaries with conservative duplicate-alarm protection."""

from __future__ import annotations

from dataclasses import dataclass

from .models import AlarmLifecycle, AlarmState, new_id


@dataclass(frozen=True, slots=True)
class AlarmKey:
    """Unique active-alarm key: one rule and one cause cannot run twice."""

    rule_id: str
    cause_key: str


class AlarmLifecycleEngine:
    """In-memory guard used by offline tests until the repository is wired to HA."""

    def __init__(self) -> None:
        self._active: dict[AlarmKey, AlarmLifecycle] = {}

    def start(self, rule_id: str, cause_key: str) -> AlarmLifecycle:
        key = AlarmKey(rule_id, cause_key)
        if key in self._active:
            raise ValueError("active alarm already exists for rule and cause")
        alarm = AlarmLifecycle(new_id(), rule_id, cause_key)
        self._active[key] = alarm
        return alarm

    def resolve(self, rule_id: str, cause_key: str, reason: str) -> AlarmLifecycle:
        key = AlarmKey(rule_id, cause_key)
        alarm = self._active.pop(key)
        return AlarmLifecycle(
            alarm.alarm_id,
            alarm.rule_id,
            alarm.cause_key,
            alarm_state=AlarmState.RESOLVED,
            acknowledgement_state=alarm.acknowledgement_state,
            delivery_state=alarm.delivery_state,
            escalation_state=alarm.escalation_state,
            closure_reason=reason,
            technical_error=alarm.technical_error,
        )

