"""Server-side revalidation of an existing alarm against current HA state."""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.core import HomeAssistant

from .evaluator import EvaluationContext, evaluate_condition, evaluate_numeric_trigger
from .rules import Comparison, RuleDefinition, TriggerDefinition, TriggerKind


@dataclass(frozen=True, slots=True)
class RevalidationResult:
    valid: bool
    safe_to_resolve: bool
    reason: str


async def async_activate_pending_revalidated(hass: HomeAssistant, alarm_store, rule_store, now: datetime):
    """Revalidate due pending alarms from HA state before activating them."""

    validations: dict[str, bool] = {}
    for alarm in await alarm_store.async_list(states=("pending",)):
        rule = await rule_store.async_get(alarm.rule_id, version=alarm.rule_version)
        result = revalidate_alarm(hass, rule, alarm, now) if rule else RevalidationResult(False, False, "Ursprüngliche Regel nicht verfügbar.")
        validations[alarm.alarm_id] = result.valid
    return await alarm_store.async_activate_pending(now=now, validations=validations)


def revalidate_alarm(hass: HomeAssistant, rule: RuleDefinition, alarm, now: datetime) -> RevalidationResult:
    """Check only the original cause and rule conditions; never create an alarm."""

    state = hass.states.get(alarm.entity_id)
    if state is None or state.state in {"unknown", "unavailable"}:
        return RevalidationResult(False, False, "Sensorzustand ist unbekannt oder nicht verfügbar.")
    trigger = next((item for item in rule.triggers if alarm.entity_id in item.entity_ids), None)
    if trigger is None:
        return RevalidationResult(False, False, "Der ursprüngliche Auslöser ist in der Regel nicht mehr vorhanden.")
    if not _trigger_matches(trigger, alarm, state, now):
        return RevalidationResult(False, True, "Die ursprüngliche Auslöseursache besteht nicht mehr.")
    context = _context(hass, rule, now)
    if _condition_has_uncertain_state(hass, rule.conditions):
        return RevalidationResult(False, False, "Eine für den Alarm relevante Bedingung ist unbekannt oder nicht verfügbar.")
    try:
        conditions_valid = evaluate_condition(rule.conditions, context)
    except (KeyError, TypeError, ValueError, OverflowError):
        return RevalidationResult(False, False, "Die Bedingungen konnten nicht sicher ausgewertet werden.")
    if not conditions_valid:
        return RevalidationResult(False, True, "Die ursprünglichen Bedingungen sind nicht mehr erfüllt.")
    return RevalidationResult(True, False, "Die ursprüngliche Auslöseursache besteht weiterhin.")


def _condition_has_uncertain_state(hass: HomeAssistant, node) -> bool:
    if node.kind in {"all", "any"}:
        return any(_condition_has_uncertain_state(hass, child) for child in node.children)
    entity_id = node.value.get("entity_id") if isinstance(node.value, dict) else None
    if not entity_id:
        return False
    state = hass.states.get(entity_id)
    return state is None or state.state in {"unknown", "unavailable"}


def _trigger_matches(trigger: TriggerDefinition, alarm, state: Any, now: datetime) -> bool:
    current = state.state
    last_changed = getattr(state, "last_changed", None)
    elapsed = (now - last_changed).total_seconds() if last_changed else 0
    if trigger.kind is TriggerKind.STATE:
        if trigger.unknown_policy.value == "ignore" and current == "unknown":
            return False
        if trigger.unavailable_policy.value == "ignore" and current == "unavailable":
            return False
        if trigger.to_state is not None and current != trigger.to_state:
            return False
        if trigger.from_state is not None and alarm.previous_state != trigger.from_state:
            return False
        return elapsed >= trigger.minimum_duration_seconds
    try:
        value = float(current)
    except (TypeError, ValueError):
        return False
    if not math.isfinite(value):
        return False
    return evaluate_numeric_trigger(
        value,
        trigger.comparison.value if trigger.comparison else Comparison.EQ.value,
        float(trigger.threshold or 0),
        upper_threshold=trigger.upper_threshold,
        previous_match=True,
        hysteresis=float(trigger.hysteresis or 0),
        elapsed_seconds=elapsed,
        minimum_duration_seconds=trigger.minimum_duration_seconds,
    )


def _context(hass: HomeAssistant, rule: RuleDefinition, now: datetime) -> EvaluationContext:
    entity_ids = {entity_id for trigger in rule.triggers for entity_id in trigger.entity_ids}
    def collect(node) -> None:
        if node.kind in {"all", "any"}:
            for child in node.children:
                collect(child)
        elif isinstance(node.value, dict) and node.value.get("entity_id"):
            entity_ids.add(node.value["entity_id"])
    collect(rule.conditions)
    states: dict[str, str] = {}
    numeric: dict[str, float] = {}
    presence: dict[str, bool | None] = {}
    for entity_id in entity_ids:
        item = hass.states.get(entity_id)
        if item is None:
            continue
        states[entity_id] = item.state
        try:
            number = float(item.state)
            if math.isfinite(number):
                numeric[entity_id] = number
        except (TypeError, ValueError):
            pass
        if item.state == "home":
            presence[entity_id] = True
        elif item.state == "not_home":
            presence[entity_id] = False
        elif item.state in {"unknown", "unavailable"}:
            presence[entity_id] = None
    return EvaluationContext(states=states, numeric_states=numeric, presence=presence, now=now)
