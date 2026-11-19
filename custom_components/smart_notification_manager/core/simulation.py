"""Read-only Phase-8 rule simulation."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from .evaluator import EvaluationContext, evaluate_condition, evaluate_numeric_trigger, evaluate_state_trigger
from .policies import quiet_hours_active
from .rule_store import rule_from_editor_payload


def simulate_rule(value: dict[str, Any], *, states: dict[str, Any] | None = None, numeric_states: dict[str, float] | None = None, presence: dict[str, bool | str | None] | None = None, now: datetime | None = None, policy_reasons: list[dict[str, str]] | None = None) -> dict[str, Any]:
    """Evaluate a draft without writing alarms, policies, rate limits or audit rows."""

    timestamp = now or datetime.now(UTC)
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ValueError("Simulationszeitpunkt muss eine Zeitzone enthalten")
    rule = rule_from_editor_payload(value)
    raw_states = states or {}
    numeric = numeric_states or {}
    presence_values = presence or {}
    trigger_results = []
    for trigger in rule.triggers:
        matched = False
        for entity_id in trigger.entity_ids:
            sample = raw_states.get(entity_id)
            before = sample.get("before") if isinstance(sample, dict) else None
            after = sample.get("after", sample.get("state")) if isinstance(sample, dict) else sample
            if trigger.kind.value == "state":
                matched = matched or evaluate_state_trigger(before, after, from_state=trigger.from_state, to_state=trigger.to_state, minimum_duration_seconds=trigger.minimum_duration_seconds, unknown_policy=trigger.unknown_policy.value, unavailable_policy=trigger.unavailable_policy.value)
            else:
                current = numeric.get(entity_id)
                if current is not None:
                    matched = matched or evaluate_numeric_trigger(current, trigger.comparison.value, trigger.threshold, upper_threshold=trigger.upper_threshold, hysteresis=trigger.hysteresis or 0, minimum_duration_seconds=trigger.minimum_duration_seconds)
        trigger_results.append({"entity_ids": list(trigger.entity_ids), "matched": bool(matched), "kind": trigger.kind.value})
    conditions = evaluate_condition(rule.conditions, EvaluationContext({key: (item.get("after", item.get("state")) if isinstance(item, dict) else item) for key, item in raw_states.items()}, numeric, presence_values, timestamp))
    reasons = list(policy_reasons or [])
    suppressed = next((item for item in reasons if item.get("action") in {"suppress", "observe"}), None)
    would_trigger = bool(trigger_results and any(item["matched"] for item in trigger_results) and conditions)
    if suppressed:
        would_send = False
        delivery_reason = suppressed.get("reason_de", suppressed["reason"])
    else:
        would_send = would_trigger
        delivery_reason = "Zustellung wäre möglich." if would_trigger else "Auslöser oder Bedingungen sind nicht erfüllt."
    return {"would_trigger": would_trigger, "would_send": would_send, "trigger_results": trigger_results, "conditions_met": conditions, "delivery_reason": delivery_reason, "policy_reasons": reasons, "affected_entities": [entity_id for trigger in rule.triggers for entity_id in trigger.entity_ids], "recipients": rule.routing.get("recipient_ids", []), "channels": rule.routing.get("channel_ids", []), "earliest_delivery": timestamp.isoformat() if would_send else None, "repeat_plan": value.get("repeat", {}), "escalation_plan": value.get("escalation", {})}


async def async_policy_preview(repository, *, rule_id: str, priority: str, now: datetime, alarm_state: str = "active", category: str | None = None, entity_id: str | None = None) -> list[dict[str, str]]:
    """Read policy tables without invoking the mutating PolicyStore decision."""

    def operation(connection):
        reasons: list[dict[str, str]] = []
        if alarm_state not in {"active", "pending", "overdue"}:
            reasons.append({"action": "suppress", "reason": "alarm_not_active", "reason_de": "Alarm ist nicht aktiv."})
        observation = connection.execute("SELECT enabled,critical_confirmed FROM observation_modes WHERE rule_id=?", (rule_id,)).fetchone()
        if observation and observation[0]:
            reasons.append({"action": "observe", "reason": "observation_mode", "reason_de": "Beobachtungsmodus: keine Zustellung."})
        for row in connection.execute("SELECT weekdays_json,start_time,end_time,timezone,rule_exceptions_json,priority_exceptions_json FROM quiet_hours WHERE enabled=1"):
            from .policies import QuietHours
            quiet = QuietHours("preview", "preview", True, tuple(json.loads(row[0])), row[1], row[2], row[3], tuple(json.loads(row[4])), tuple(json.loads(row[5])))
            if quiet_hours_active(quiet, now, rule_id=rule_id, priority=priority):
                reasons.append({"action": "suppress", "reason": "quiet_hours", "reason_de": "Ruhezeit ist aktiv."})
        for row in connection.execute("SELECT scope_type,scope_id,starts_at,ends_at FROM notification_pauses WHERE active=1"):
            if datetime.fromisoformat(row[2]) <= now and (not row[3] or datetime.fromisoformat(row[3]) > now) and (row[0] == "global" or (row[0] == "rule" and row[1] == rule_id) or (row[0] == "category" and row[1] == category) or (row[0] == "entity" and row[1] == entity_id)) and priority != "critical":
                reasons.append({"action": "suppress", "reason": "paused", "reason_de": "Die Benachrichtigung ist pausiert."})
        return reasons

    return await repository.async_run(operation)
