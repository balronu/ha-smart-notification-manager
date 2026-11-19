"""Read-only Phase-8 rule simulation."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from .evaluator import EvaluationContext, evaluate_condition, evaluate_numeric_trigger, evaluate_state_trigger
from .policies import PolicyStore
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
    required_entities = {entity_id for trigger in rule.triggers for entity_id in trigger.entity_ids}
    required_entities.update(
        child.value["entity_id"]
        for child in _condition_nodes(rule.conditions)
        if isinstance(child.value, dict) and child.value.get("entity_id")
    )
    supplied_entities = set(raw_states) | set(numeric) | set(presence_values)
    data_complete = required_entities <= supplied_entities
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
    would_trigger = bool(data_complete and trigger_results and any(item["matched"] for item in trigger_results) and conditions)
    if suppressed:
        would_send = False
        delivery_reason = suppressed.get("reason_de", suppressed["reason"])
    elif not data_complete:
        would_send = False
        delivery_reason = "Nicht sicher bestimmbar: Zustandsdaten fehlen."
    else:
        would_send = would_trigger
        delivery_reason = "Zustellung wäre möglich." if would_trigger else "Auslöser oder Bedingungen sind nicht erfüllt."
    delay = max((trigger.delay_seconds for trigger in rule.triggers), default=0)
    earliest = timestamp + timedelta(seconds=delay) if would_send else None
    return {"would_trigger": would_trigger, "would_send": would_send, "data_complete": data_complete, "trigger_results": trigger_results, "conditions_met": conditions, "delivery_reason": delivery_reason, "policy_reasons": reasons, "affected_entities": [entity_id for trigger in rule.triggers for entity_id in trigger.entity_ids], "recipients": rule.routing.get("recipient_ids", []), "channels": rule.routing.get("channel_ids", []), "earliest_delivery": earliest.isoformat() if earliest else None, "repeat_plan": value.get("repeat", {}), "escalation_plan": value.get("escalation", {})}


async def async_policy_preview(repository, *, rule_id: str, priority: str, now: datetime, alarm_state: str = "active", category: str | None = None, entity_id: str | None = None) -> list[dict[str, str]]:
    """Read the central policy decision without recording or reserving anything."""
    preview = await repository.async_run(
        lambda connection: PolicyStore(repository).preview_in_connection(
            connection,
            {"rule_id": rule_id, "priority": priority, "alarm_state": alarm_state, "category": category, "entity_id": entity_id},
            now=now,
        )
    )
    reason = {"action": preview.decision.action, "reason": preview.decision.reason_code, "reason_de": preview.decision.reason_de}
    if preview.remaining_capacity is not None:
        reason["remaining_capacity"] = str(preview.remaining_capacity)
    return [reason]


def _condition_nodes(node):
    yield node
    for child in node.children:
        yield from _condition_nodes(child)
